# Verified Claim Engine

ChIAtraton tratează AI-ul ca pe un motor de afirmații verificabile, nu ca pe un
chatbot RAG care răspunde direct din primul context găsit.

```text
PDF
 -> sursă structurată și auditabilă
 -> căutare exhaustivă sau retrieval orientat pe recall
 -> claim-uri atomice
 -> verificări independente
 -> decizie deterministă
 -> VERIFIED / RETRY / ABSTAIN
```

## Invariantă Principală

LLM-urile pot propune, reformula și interpreta. Numai textul original al
documentului poate constitui evidence. O afirmație nu este prezentată drept
verificată până când trece validările deterministe și verificările semantice
cerute de fluxul respectiv.

## Claim vs Evidence

Un `statement` este o formulare AI, utilă pentru UI și pentru review. Nu este un
citat.

Evidence-ul este separat și provine din document:

```text
GroundedClaim.statement:
  Ținta RCO01 este 1 întreprindere.

Evidence:
  pagina 27: Indicator: RCO01
  pagina 27: Țintă: 1,000
  pagina 27: Unitate de măsură: întreprinderi
```

Această separare evită dilema în care o celulă izolată este prea scurtă, iar un
rând întreg de tabel devine prea lat și zgomotos.

## Unități Atomice

Regula de bază este:

```text
1 claim = 1 fapt verificabil independent
```

Un paragraf care menționează cotă de piață, cifră de afaceri, angajări și cash
flow trebuie să producă mai multe claim-uri, nu un card compozit.

## Roluri De Verificare

Verifierii nu votează. Ei verifică proprietăți diferite:

- `provenance`: evidence-ul există exact pe pagina declarată;
- `entailment`: evidence-ul susține claim-ul;
- `adversarial`: nu există contradicții sau calificări care schimbă sensul;
- `completeness`: răspunsul este complet pentru întrebare;
- `numeric`: operațiile matematice sunt calculate determinist.

Acceptarea nu este `2 din 3`. Este o decizie deterministă:

```python
verified = (
    provenance_passed
    and entailment_passed
    and not contradiction_found
    and completeness_passed
    and numeric_checks_passed
)
```

## Arbiter Determinist

Modulul `AI.claim_engine` definește primitivele interne:

- `EvidenceRef`
- `GroundedClaim`
- `VerificationResult`
- `VerifiedClaim`
- `Answer`

și funcțiile:

- `provenance_verification`
- `compute_numeric_operation`
- `decide_claim`
- `assemble_answer`

Acestea sunt provider-agnostic. Integrarea cu OpenAI, Anthropic, Google sau alți
verifieri se face prin adaptoare separate. Arbiterul local rămâne determinist și
nu face majority voting.

## Două Căi De Răspuns

Întrebările punctuale pot folosi retrieval:

```text
question -> planner -> evidence pool -> generator -> verifieri -> answer
```

Întrebările exhaustive, inclusiv extracția obligațiilor, folosesc map/reduce:

```text
all source candidates
 -> discovery batches + complete source coverage ledger
 -> closed-taxonomy claim review batches
 -> deterministic provenance / acceptance checks
 -> global precision selection and duplicate/subclaim removal
 -> proposed obligations
```

Reviewer-ul nu produce direct o listă liberă de obligații. El trebuie să emită
exact un verdict pentru fiecare claim primit și abaterea de baseline produsă de
neîndeplinire pentru fiecare claim păstrat. Selecția finală vede global claim-urile
validate provizoriu, elimină contextul și atributele desprinse și alege o singură
formulare grounded pentru aceeași obligație. Nu formulează text nou.

Extractorul de obligații existent este specializarea acestei a doua căi:

```text
What are all independently monitorable obligations defined by this document?
```

## DocumentGraph

Direcția țintă este ca infrastructura centrală să fie un `DocumentGraph`, nu doar
o listă de chunk-uri. Relațiile care trebuie păstrate explicit:

- cell -> row -> table -> page;
- selected option -> criterion -> selection marker;
- indicator value -> indicator name -> unit;
- paragraph -> section -> page.

Până la migrarea completă, `StructuredBlock.source_text`, `SourceUnit` și
`SourceAnchor` păstrează invarianta de evidence exact.

## Caching

Verificările pot fi cache-uite după:

```text
hash(question + claim + evidence_ids + verifier_model_version)
```

Un viitor `VerifiedFactGraph` per document poate pre-calcula fapte precum ținte,
contribuții, termene și obligații recurente, dar răspunsul final trebuie să
revalideze provenance-ul înainte de afișare.
