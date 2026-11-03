#!/usr/bin/env python3
"""
extract.py - rule-based triple extractor for AI3001 Assignment 1.

Reads plain-text documents from data/raw/, uses spaCy (sentence splitting,
entity labels, dependency parse) and hand-written rules to extract five
predicates: bornIn, educatedAt, receivedAward, worksAt, doctoralAdvisor.

Output: a CSV with columns subject, predicate, object, source_doc, sentence
        plus a merge report (alias merges) next to it.

Usage:
    python src/extract.py                                  # all files in data/raw
    python src/extract.py --only private_document.txt \
           --out /tmp/test_triples.csv -v                  # one file, verbose

No relation-extraction model and no LLM is used: every triple comes from
the rules in this file.
"""
import argparse
import csv
import pathlib
import re
from collections import defaultdict

import spacy

# --------------------------------------------------------------------------
# Small word lists used by the rules
# --------------------------------------------------------------------------
TITLES = {"dr", "prof", "professor", "sir", "mr", "mrs", "ms", "miss", "lord",
          "lady", "dame", "rev", "fr", "herr", "frau", "sr", "jr"}

ORG_KW = {"university", "college", "institute", "institution", "school",
          "academy", "laboratory", "laboratories", "lab", "polytechnic",
          "observatory", "foundation", "society", "gymnasium", "hochschule",
          "universität", "universitat", "centre", "center", "council",
          "company", "corporation", "department", "faculty", "seminary"}

EDU_KW = {"university", "college", "institute", "school", "academy",
          "polytechnic", "gymnasium", "hochschule", "universität", "seminary"}

AWARD_KW = {"prize", "medal", "award", "cross", "honour", "honor", "fellowship"}

DEGREE_NOUNS = {"phd", "ph.d.", "ph.d", "doctorate", "degree", "diploma",
                "bachelor", "master", "ba", "ma", "bsc", "msc", "dsc",
                "dphil", "habilitation", "licentiate"}

ROLE_NOUNS = {"professor", "professorship", "chair", "lecturer", "lectureship",
              "director", "researcher", "assistant", "position", "post",
              "fellow", "scientist", "instructor", "reader"}

ADVISOR_NOUNS = {"advisor", "adviser", "supervisor"}
ADVISOR_MODS = {"doctoral", "phd", "ph.d.", "thesis", "doctorate", "dissertation"}
THESIS_WORDS = {"phd", "ph.d.", "ph.d", "doctorate", "doctoral", "thesis",
                "dissertation", "dphil"}

NEG_WORDS = {"never", "not", "n't", "neither", "nor", "hardly", "barely"}

PRON_GENDER = {"he": "m", "him": "m", "his": "m", "himself": "m",
               "she": "f", "her": "f", "hers": "f", "herself": "f"}

# Tiny first-name seed lexicon; unknown names get their gender learned from
# the first pronoun that resolves to them (see Ctx.resolve_pronoun).
MALE = {"james", "steven", "albert", "ernest", "john", "robert", "max", "hans",
        "otto", "niels", "junaid", "ahmed", "muhammad", "ali", "hassan",
        "william", "charles", "edward", "paul", "walter", "werner", "erwin",
        "arnold", "enrico", "george", "henry", "thomas", "richard", "frank",
        "hermann", "wolfgang", "isidor", "robert", "arthur", "ludwig"}
FEMALE = {"Khansa", "mileva", "elsa", "maria", "marie", "lise", "mary", "anna",
          "emmy", "ida", "irene", "sara", "fatima", "ayesha", "sana", "nadia",
          "margaret", "elizabeth", "rosalind", "maja"}

RELATION_TYPES = ["bornIn", "educatedAt", "receivedAward", "worksAt",
                  "doctoralAdvisor"]


# --------------------------------------------------------------------------
# Helpers for names and spans
# --------------------------------------------------------------------------
def clean_name(s):
    """Strip possessive 's, titles (Dr., Sir ...) and stray punctuation."""
    s = s.replace(" ", " ").strip()
    s = re.sub(r"['’]s$", "", s)
    words = [w for w in s.split() if w.strip(".").lower() not in TITLES]
    return " ".join(words).strip(" ,.;:\"'()[]")


def join_tokens(tokens):
    """Join tokens back into text, keeping original spacing when adjacent."""
    tokens = sorted(set(tokens), key=lambda t: t.i)
    out = ""
    for k, t in enumerate(tokens):
        out += t.text
        if k + 1 < len(tokens):
            nxt = tokens[k + 1]
            out += t.whitespace_ if nxt.i == t.i + 1 else " "
    return out.strip()


def span_tokens(tok, allow_preps=()):
    """Tokens of a proper-noun phrase headed by `tok`.

    Takes capitalised compound/amod modifiers on the left and, for the given
    prepositions, a capitalised object on the right ('College of Science').
    Determiners ('the') and dates are left out.
    """
    toks = [tok]
    for c in tok.lefts:
        if c.dep_ in ("compound", "amod", "nmod") and (
                c.pos_ == "PROPN" or c.text[:1].isupper()):
            toks.extend(span_tokens(c))
    for p in tok.rights:
        if p.dep_ == "prep" and p.lower_ in allow_preps:
            for o in p.children:
                if o.dep_ == "pobj" and o.ent_type_ != "DATE" and (
                        o.pos_ == "PROPN" or o.text[:1].isupper()):
                    toks.append(p)
                    toks.extend(span_tokens(o, allow_preps))
    return toks


def conj_chain(tok):
    return [tok] + list(tok.conjuncts)


def get_subject(v):
    """Subject token of a verb; follows 'X studied ... and worked ...' (conj)
    and relative/participle clauses ('Einstein, born in Ulm')."""
    for c in v.children:
        if c.dep_ in ("nsubj", "nsubjpass"):
            return c
    if v.dep_ == "conj":
        return get_subject(v.head)
    if v.dep_ in ("acl", "relcl") and v.head.pos_ in ("PROPN", "NOUN"):
        return v.head
    return None


def negated(v):
    """True if the verb is negated ('never studied', 'did not join')."""
    for c in v.children:
        if c.dep_ == "neg" or c.lower_ in NEG_WORDS:
            return True
    return False


def looks_org(text, root):
    words = {w.strip(",.").lower() for w in text.split()}
    return bool(words & ORG_KW) or root.ent_type_ in ("ORG", "FAC")


def has_edu_kw(text):
    return bool({w.strip(",.").lower() for w in text.split()} & EDU_KW)


# --------------------------------------------------------------------------
# Entity registry: one canonical name per real person (alias merging)
# --------------------------------------------------------------------------
class Registry:
    def __init__(self):
        self.full = set()
        self.by_surname = defaultdict(set)
        self.main = {}  # doc name -> main subject name

    def add(self, name):
        parts = name.split()
        if len(parts) >= 2:
            self.full.add(name)
            self.by_surname[parts[-1].lower()].add(name)

    def canonical(self, surface, doc_name=None):
        s = clean_name(surface)
        if not s:
            return None
        if s in self.full:
            return s
        parts = s.split()
        if len(parts) == 1:
            cands = self.by_surname.get(s.lower())
            if cands:
                if len(cands) == 1:
                    return next(iter(cands))
                main = self.main.get(doc_name)
                if main in cands:
                    return main
                return sorted(cands)[0]
        return s

    def is_surname(self, word):
        return word.lower() in self.by_surname


def is_person_head(tok, registry):
    """Is `tok` the head token of a person-name mention?"""
    if tok.pos_ != "PROPN":
        return False
    if not (tok.ent_type_ == "PERSON" or registry.is_surname(tok.text)):
        return False
    if tok.dep_ == "compound" and tok.head.i > tok.i and tok.head.pos_ == "PROPN" \
            and (tok.head.ent_type_ == "PERSON" or registry.is_surname(tok.head.text)):
        return False  # first-name part of a longer name
    words = {w.lower() for w in person_surface(tok, keep_titles=True).split()}
    if words & (ORG_KW | AWARD_KW):
        return False  # NER sometimes calls prizes/institutes PERSON
    return True


def person_surface(tok, keep_titles=False):
    parts = [c.text for c in tok.lefts if c.dep_ == "compound" and (
        c.pos_ == "PROPN" or c.text.strip(".").lower() in TITLES)]
    raw = " ".join(parts + [tok.text])
    return raw if keep_titles else clean_name(raw)


# --------------------------------------------------------------------------
# Per-document context: pronoun resolution
# --------------------------------------------------------------------------
class Mention:
    def __init__(self, name, role, i):
        self.name, self.role, self.i = name, role, i


class Ctx:
    def __init__(self, doc_name, main, registry):
        self.doc_name = doc_name
        self.main = main
        self.registry = registry
        self.history = []   # list (per finished sentence) of [Mention]
        self.cur = []       # mentions in the sentence being processed
        self.gender = {}    # learned genders: name -> 'm' | 'f'

    def gender_of(self, name):
        if name in self.gender:
            return self.gender[name]
        first = name.split()[0].lower()
        if first in MALE:
            return "m"
        if first in FEMALE:
            return "f"
        return None

    def resolve_pronoun(self, tok):
        """he/she/his/her -> a name, or None when no compatible candidate.

        Candidates, best first: earlier mentions in this sentence, the
        previous sentence (subjects before objects), older sentences by
        recency, then the document's main subject. A candidate is skipped
        when its known gender disagrees with the pronoun; this is how
        'He later moved ...' is NOT attached to the female main subject.
        """
        g = PRON_GENDER.get(tok.lower_)
        if g is None:
            return None
        cands = [m.name for m in sorted(self.cur, key=lambda m: -m.i)
                 if m.i < tok.i]
        order = lambda m: (m.role != "subj", m.i)
        if self.history:
            cands += [m.name for m in sorted(self.history[-1], key=order)]
        if self.main:
            cands.append(self.main)
        for past in reversed(self.history[:-1]):
            cands += [m.name for m in sorted(past, key=order)]
        seen = set()
        for name in cands:
            if name in seen:
                continue
            seen.add(name)
            cg = self.gender_of(name)
            if cg is None or cg == g:
                if cg is None:
                    self.gender[name] = g   # learn gender from the pronoun
                return name
        return None

    def person(self, tok):
        """Token -> canonical person name (or None if it isn't a person)."""
        if tok is None:
            return None
        if tok.tag_ in ("PRP", "PRP$"):
            return self.resolve_pronoun(tok)
        if is_person_head(tok, self.registry):
            return self.registry.canonical(person_surface(tok), self.doc_name)
        # 'His wife Lise Meyer studied ...': subject noun with a named apposition
        for c in tok.children:
            if c.dep_ in ("appos", "compound") and is_person_head(c, self.registry):
                return self.registry.canonical(person_surface(c), self.doc_name)
        return None


# --------------------------------------------------------------------------
# The extractor
# --------------------------------------------------------------------------
class Extractor:
    def __init__(self, registry):
        self.registry = registry
        self.triples = []        # dicts
        self.suppressed = []     # negated statements (for the report)
        self.merge_pairs = {}    # (alias, canonical) -> count
        self.rule_hits = defaultdict(int)

    # ---- bookkeeping ----------------------------------------------------
    def add(self, subj, pred, obj, doc_name, sent, rule):
        if not subj or not obj or subj == obj:
            return
        self.triples.append({
            "subject": subj, "predicate": pred, "object": obj,
            "source_doc": doc_name,
            "sentence": re.sub(r"\s+", " ", sent.text).strip(),
            "_rule": rule})
        self.rule_hits[rule] += 1

    def suppress(self, subj, pred, obj, doc_name, sent, why):
        self.suppressed.append((subj, pred, obj, doc_name,
                                re.sub(r"\s+", " ", sent.text).strip(), why))

    # ---- one sentence ---------------------------------------------------
    def process_sentence(self, sent, ctx):
        ctx.cur = []
        for tok in sent:
            if is_person_head(tok, self.registry):
                raw = person_surface(tok, keep_titles=True)
                canon = self.registry.canonical(person_surface(tok), ctx.doc_name)
                if canon:
                    role = "subj" if tok.dep_ in ("nsubj", "nsubjpass") else "other"
                    ctx.cur.append(Mention(canon, role, tok.i))
                    if raw != canon:   # alias merged into the full name
                        key = (raw, canon)
                        self.merge_pairs[key] = self.merge_pairs.get(key, 0) + 1

        for tok in sent:
            self.rule_born(tok, sent, ctx)
            self.rule_education(tok, sent, ctx)
            self.rule_degree(tok, sent, ctx)
            self.rule_award(tok, sent, ctx)
            self.rule_join_work(tok, sent, ctx)
            self.rule_role_noun(tok, sent, ctx)
            self.rule_advisor_noun(tok, sent, ctx)
            self.rule_advisor_verb(tok, sent, ctx)
            self.rule_advisor_under(tok, sent, ctx)
        ctx.history.append(ctx.cur)

    # ---- R1 bornIn (dependency: born -> prep(in/at) -> pobj) -------------
    def rule_born(self, tok, sent, ctx):
        if tok.lower_ != "born":
            return
        subj = ctx.person(get_subject(tok))
        for p in tok.children:
            if p.dep_ == "prep" and p.lower_ in ("in", "at"):
                for o in p.children:
                    if o.dep_ != "pobj" or o.pos_ != "PROPN":
                        continue
                    if o.ent_type_ in ("DATE", "CARDINAL", "PERSON"):
                        continue
                    place = join_tokens(span_tokens(o))
                    if negated(tok):
                        self.suppress(subj, "bornIn", place, ctx.doc_name, sent, "negation")
                    else:
                        self.add(subj, "bornIn", place, ctx.doc_name, sent, "R1-born")

    # ---- R2 educatedAt (dependency: study/attend/graduate verbs) ---------
    def rule_education(self, tok, sent, ctx):
        if tok.pos_ != "VERB" or tok.lemma_ not in (
                "study", "graduate", "attend", "educate", "enrol", "enroll",
                "matriculate", "enter"):
            return
        subj = ctx.person(get_subject(tok))
        if subj is None:
            return
        objs = []
        for c in tok.children:
            if c.dep_ == "prep" and c.lower_ in ("at", "from", "in"):
                objs += [(o, c.lower_) for o in c.children if o.dep_ == "pobj"]
            elif c.dep_ == "dobj" and tok.lemma_ in ("attend", "enter"):
                objs.append((c, "dobj"))
        for o, how in objs:
            for o2 in conj_chain(o):
                if o2.pos_ != "PROPN" or o2.ent_type_ in ("DATE", "CARDINAL"):
                    continue
                text = join_tokens(span_tokens(o2, allow_preps=("of", "for")))
                if tok.lemma_ == "enter" or how == "in":
                    if not has_edu_kw(text):      # 'in Berlin' is not a school
                        continue
                if o2.ent_type_ == "PERSON" and not looks_org(text, o2):
                    continue
                if negated(tok):
                    self.suppress(subj, "educatedAt", text, ctx.doc_name, sent, "negation")
                else:
                    self.add(subj, "educatedAt", text, ctx.doc_name, sent, "R2-study")

    # ---- R2b educatedAt via degree ('received his PhD from X') -----------
    def rule_degree(self, tok, sent, ctx):
        if tok.pos_ != "VERB" or tok.lemma_ not in (
                "receive", "earn", "obtain", "complete", "gain", "take"):
            return
        degs = [c for c in tok.children if c.dep_ == "dobj"
                and c.lower_.strip(".") in DEGREE_NOUNS]
        if not degs:
            return
        subj = ctx.person(get_subject(tok))
        if subj is None:
            return
        holders = [tok] + degs
        for h in holders:
            for p in h.children:
                if p.dep_ == "prep" and p.lower_ in ("from", "at"):
                    for o in p.children:
                        if o.dep_ == "pobj" and o.pos_ == "PROPN" \
                                and o.ent_type_ not in ("DATE", "CARDINAL"):
                            text = join_tokens(span_tokens(o, ("of", "for")))
                            if negated(tok):
                                self.suppress(subj, "educatedAt", text, ctx.doc_name, sent, "negation")
                            else:
                                self.add(subj, "educatedAt", text, ctx.doc_name, sent, "R2b-degree")

    # ---- R3 receivedAward (dependency: receive/win/award + dobj) ---------
    def rule_award(self, tok, sent, ctx):
        if tok.pos_ != "VERB" or tok.lemma_ not in (
                "receive", "win", "earn", "award", "share", "accept"):
            return
        if tok.lemma_ == "award":
            rec = [c for c in tok.children if c.dep_ in ("dative", "iobj")]
            subj_tok = rec[0] if rec else get_subject(tok)
            if not rec and not any(c.dep_ == "nsubjpass" for c in tok.children):
                return           # active 'The jury awarded a prize': no recipient
        else:
            subj_tok = get_subject(tok)
        subj = ctx.person(subj_tok)
        if subj is None:
            return
        for d in [c for c in tok.children if c.dep_ == "dobj"]:
            for o in conj_chain(d):
                toks = span_tokens(o, allow_preps=("in", "of"))
                text = join_tokens(toks)
                if not ({t.lower_ for t in toks} & AWARD_KW):
                    continue
                if negated(tok):
                    self.suppress(subj, "receivedAward", text, ctx.doc_name, sent, "negation")
                else:
                    self.add(subj, "receivedAward", text, ctx.doc_name, sent, "R3-award")

    # ---- R4 worksAt (dependency: join + dobj / work + prep / move to) ----
    def rule_join_work(self, tok, sent, ctx):
        if tok.pos_ != "VERB":
            return
        lem = tok.lemma_
        if lem not in ("join", "work", "teach", "lecture", "move", "relocate",
                       "transfer"):
            return
        subj = ctx.person(get_subject(tok))
        if subj is None:
            return
        objs = []
        for c in tok.children:
            if lem == "join" and c.dep_ == "dobj":
                objs += conj_chain(c)
            elif lem in ("work", "teach", "lecture") and c.dep_ == "prep" \
                    and c.lower_ in ("at", "for", "in"):
                objs += [o for o in c.children if o.dep_ == "pobj"]
            elif lem in ("move", "relocate", "transfer") and c.dep_ == "prep" \
                    and c.lower_ == "to":
                objs += [o for o in c.children if o.dep_ == "pobj"]
        for o in objs:
            for o2 in conj_chain(o):
                if o2.pos_ != "PROPN" or o2.ent_type_ in ("DATE", "CARDINAL"):
                    continue
                text = join_tokens(span_tokens(o2, allow_preps=("of", "for")))
                if not looks_org(text, o2):
                    continue                  # 'moved to Berlin' is not an employer
                if negated(tok):
                    self.suppress(subj, "worksAt", text, ctx.doc_name, sent, "negation")
                else:
                    self.add(subj, "worksAt", text, ctx.doc_name, sent, "R4-join")

    # ---- R4b worksAt via role noun ('became professor at X') -------------
    def rule_role_noun(self, tok, sent, ctx):
        if tok.lower_ not in ROLE_NOUNS or tok.dep_ not in ("attr", "dobj", "oprd", "pobj"):
            return
        verb = tok.head
        if tok.dep_ == "pobj":                 # 'appointed to a chair at X'
            verb = tok.head.head if tok.head.dep_ == "prep" else verb
        if verb.pos_ not in ("VERB", "AUX"):
            return
        subj = ctx.person(get_subject(verb))
        if subj is None:
            return
        found = []
        for p in list(tok.subtree) + list(verb.children):
            if p.dep_ == "prep" and p.lower_ in ("at", "for"):
                found += [o for o in p.children if o.dep_ == "pobj"]
        for o in found:
            if o.pos_ != "PROPN" or o.ent_type_ in ("DATE", "CARDINAL"):
                continue
            text = join_tokens(span_tokens(o, allow_preps=("of", "for")))
            if not looks_org(text, o):
                continue
            if negated(verb):
                self.suppress(subj, "worksAt", text, ctx.doc_name, sent, "negation")
            else:
                self.add(subj, "worksAt", text, ctx.doc_name, sent, "R4b-role")

    # ---- R5 doctoralAdvisor (dependency: "X's doctoral advisor was Y") ---
    def rule_advisor_noun(self, tok, sent, ctx):
        if tok.lower_ not in ADVISOR_NOUNS:
            return
        if not any(c.lower_.strip(".") in ADVISOR_MODS for c in tok.children
                   if c.dep_ in ("amod", "compound", "nmod")):
            return
        poss = [c for c in tok.children if c.dep_ == "poss"]
        if not poss:
            return
        student = ctx.person(poss[0])
        cop = tok.head
        # 'X's doctoral advisor was Y'   (advisor = nsubj, Y = attr)
        if tok.dep_ in ("nsubj", "nsubjpass"):
            for a in [c for c in cop.children if c.dep_ in ("attr", "acomp")]:
                for a2 in conj_chain(a):
                    adv = ctx.person(a2)
                    if adv and not negated(cop):
                        self.add(student, "doctoralAdvisor", adv, ctx.doc_name, sent, "R5-advisor-noun")
        # 'Y was X's doctoral advisor'   (Y = nsubj, advisor = attr)
        elif tok.dep_ == "attr":
            adv = ctx.person(get_subject(cop))
            if adv and not negated(cop):
                self.add(student, "doctoralAdvisor", adv, ctx.doc_name, sent, "R5-advisor-noun")

    def rule_advisor_verb(self, tok, sent, ctx):
        """'Y supervised X's doctorate' / 'X was supervised by Y'."""
        if tok.pos_ != "VERB" or tok.lemma_ not in ("supervise", "advise"):
            return
        if not ({t.lower_.strip(".") for t in sent} & THESIS_WORDS):
            return
        if negated(tok):
            return
        agents = [o for c in tok.children if c.dep_ == "agent"
                  for o in c.children if o.dep_ == "pobj"]
        passive = [c for c in tok.children if c.dep_ == "nsubjpass"]
        if passive and agents:
            self.add(ctx.person(passive[0]), "doctoralAdvisor",
                     ctx.person(agents[0]), ctx.doc_name, sent, "R5-advisor-verb")
            return
        subj = get_subject(tok)
        for d in [c for c in tok.children if c.dep_ == "dobj"]:
            owner = [c for c in d.children if c.dep_ == "poss"]
            stud = ctx.person(owner[0]) if owner else ctx.person(d)
            self.add(stud, "doctoralAdvisor", ctx.person(subj), ctx.doc_name, sent,
                     "R5-advisor-verb")

    def rule_advisor_under(self, tok, sent, ctx):
        """'completed his PhD under Y' (needs a thesis word in the sentence)."""
        if tok.dep_ != "prep" or tok.lower_ != "under":
            return
        if not ({t.lower_.strip(".") for t in sent} & THESIS_WORDS):
            return
        verb = tok.head
        if verb.pos_ not in ("VERB", "AUX"):
            return
        student = ctx.person(get_subject(verb))
        for o in tok.children:
            if o.dep_ == "pobj":
                for o2 in conj_chain(o):
                    adv = ctx.person(o2)
                    if adv and student and not negated(verb):
                        self.add(student, "doctoralAdvisor", adv, ctx.doc_name, sent,
                                 "R5-advisor-under")


# --------------------------------------------------------------------------
# Driver
# --------------------------------------------------------------------------
def load_text(path):
    text = path.read_text(encoding="utf-8")
    lines = [ln for ln in text.splitlines() if not re.match(r"^\s*=+.*=+\s*$", ln)]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default="data/raw")
    ap.add_argument("--out", default="out/triples.csv")
    ap.add_argument("--only", nargs="*", help="process only these file names")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    files = sorted(pathlib.Path(args.raw).glob("*.txt"))
    if args.only:
        files = [f for f in files if f.name in args.only]
    if not files:
        raise SystemExit(f"no .txt files found in {args.raw}")

    nlp = spacy.load("en_core_web_sm")
    nlp.max_length = 3_000_000
    registry = Registry()

    # Pass 1: parse everything, build the name registry.
    docs = []
    for f in files:
        doc = nlp(load_text(f))
        docs.append((f, doc))
        if f.stem != "private_document":
            main_name = f.stem.replace("_", " ")
            registry.add(main_name)
            registry.main[f.name] = main_name
        for tok in doc:
            if is_person_head(tok, registry) and tok.ent_type_ == "PERSON":
                registry.add(person_surface(tok))
    # The invented person of the private document is the main subject there.
    for f, doc in docs:
        if f.stem == "private_document":
            first = next((t for t in doc if is_person_head(t, registry)), None)
            if first is not None:
                registry.main[f.name] = person_surface(first)

    # Pass 2: sentence by sentence extraction.
    ex = Extractor(registry)
    for f, doc in docs:
        ctx = Ctx(f.name, registry.main.get(f.name), registry)
        for sent in doc.sents:
            ex.process_sentence(sent, ctx)

    # Deduplicate and write.
    seen, rows = set(), []
    for t in ex.triples:
        key = (t["subject"], t["predicate"], t["object"], t["source_doc"], t["sentence"])
        if key not in seen:
            seen.add(key)
            rows.append(t)
    rows.sort(key=lambda t: (t["source_doc"], t["subject"], t["predicate"], t["object"]))

    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    cols = ["subject", "predicate", "object", "source_doc", "sentence"]
    with out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)

    # Merge report.
    total = sum(ex.merge_pairs.values())
    report = [f"Alias merges: {total} mentions merged into a full name "
              f"({len(ex.merge_pairs)} distinct alias forms)"]
    for (alias, canon), n in sorted(ex.merge_pairs.items()):
        report.append(f"  {alias!r} -> {canon!r}  x{n}")
    out.with_name("merge_report.txt").write_text("\n".join(report) + "\n", encoding="utf-8")

    print(f"{len(rows)} triples written to {out}")
    print("\n".join(report))
    by_pred = defaultdict(int)
    for r in rows:
        by_pred[r["predicate"]] += 1
    print("per predicate:", {p: by_pred.get(p, 0) for p in RELATION_TYPES})
    print(f"suppressed (negated): {len(ex.suppressed)}")
    if args.verbose:
        for r in rows:
            print(f"  ({r['subject']}, {r['predicate']}, {r['object']})  [{r['_rule']}]")
        for s in ex.suppressed:
            print(f"  SUPPRESSED {s[:3]} because {s[5]}: {s[4]}")


if __name__ == "__main__":
    main()