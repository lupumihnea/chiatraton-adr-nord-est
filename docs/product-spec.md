# Specificație de produs

## 1. Scop

Aplicația este un **AI Monitoring Copilot pentru ADR Nord-Est**. Ea organizează documentele și criteriile unui proiect, analizează rapoarte periodice, propune constatări verificabile și solicită decizia finală a utilizatorului.

Produsul urmărește să reducă timpul de lectură și comparare, fără a delega AI-ului autoritatea administrativă sau juridică.

## 2. Actor

Există un singur actor de business: **utilizatorul**. În versiunea curentă nu există roluri distincte pentru beneficiar, evaluator, administrator sau modelul AI. Qwen este o dependență tehnică, nu actor de business.

## 3. Terminologie canonică

- `Project`: unitatea monitorizată; conține documente, criterii și calendarul de monitorizare.
- `Document`: fișier-sursă asociat unui proiect, inclusiv documentul unui raport.
- `Criterion`: condiție verificabilă și versionată a proiectului.
- `Report`: raport periodic primit de proiect pentru o perioadă determinată.
- `SourceAnchor`: trimitere exactă la un `Document`, prin pagină și pasaj.
- `CriterionValidation`: rezultatul verificării unui singur `Criterion` pentru un singur `Report`.
- `UserDecision`: hotărârea explicită a utilizatorului asupra unei propuneri AI.
- `AnalysisJob`: execuția asincronă care analizează un raport și produce propuneri de validare.

Pentru contractele noi se folosește `criteria`, nu `obligations`. Pentru lucrul asincron se folosește `AnalysisJob`, nu denumirea generică `Task`.

## 4. Cerințe funcționale

### 4.1 Configurarea proiectului

Utilizatorul poate crea un `Project`, îi poate stabili data finalizării și `monitoringEndDate` și îi poate atașa `Document`. `monitoringEndDate` este data contractuală explicită până la care proiectul primește rapoarte și trebuie să fie egală cu sau ulterioară datei finalizării.

### 4.2 Stabilirea criteriilor

AI-ul poate propune `Criterion` din documentele proiectului. Utilizatorul confirmă sau corectează baza inițială înainte ca aceasta să fie folosită la monitorizare. Fiecare criteriu păstrează sursa din care a fost derivat.

### 4.3 Primirea rapoartelor

Un `Project` primește `Report` periodice. Produsul trebuie să poată reprezenta cel puțin rapoarte de progres din implementare, raportul final și rapoarte de durabilitate post-implementare, fără a presupune aceeași cadență pentru toate tipurile.

Rapoartele continuă până la `monitoringEndDate`. Cadența este metadată a raportului sau a proiectului, nu logică fixată în UI. Un raport are exact un document principal și poate avea mai multe documente suport.

Statusul intern ChIAtraton este separat de `externalStatus`. Un raport poate păstra `externalSystem`, `externalId`, `externalUrl` și `externalStatus` fără a executa acțiuni în MyADR/MySMIS.

### 4.4 Analiza

Încărcarea unui raport poate porni un `AnalysisJob`. Pentru fiecare pereche (`Report`, `Criterion`) se creează o `CriterionValidation` separată. Nu se omite un criteriu doar pentru că AI-ul îl consideră conform.

Fiecare constatare trebuie să includă cel puțin un `SourceAnchor` complet:

- identificatorul documentului;
- numărul paginii;
- pasajul exact folosit ca dovadă.

Dacă pagina sau pasajul nu pot fi determinate, rezultatul nu poate fi prezentat ca o constatare susținută; starea sa este `insufficient_evidence`.

### 4.5 Decizia utilizatorului

AI-ul propune o stare, o explicație și sursele. Utilizatorul ia decizia finală prin `UserDecision`: confirmă, corectează sau respinge. Un comentariu poate recomanda un follow-up în sistemul extern, dar ChIAtraton nu pornește o clarificare oficială.

Interfața poate prioritiza excepțiile, dar finalizarea unui raport nu trebuie să transforme automat propunerile AI în decizii umane.

### 4.6 Istoric

Datele sunt izolate pe raport. Validarea Raportului 2 nu suprascrie validarea Raportului 1. Reanalizarea aceluiași raport produce o nouă revizie auditabilă; nu șterge propunerea, sursele sau decizia anterioară.

## 5. Reguli și invariante

1. Orice `Document`, `Criterion` și `Report` aparține unui `Project`.
2. O `CriterionValidation` identifică exact un `Report` și un `Criterion`.
3. Pentru fiecare raport finalizat există o validare pentru fiecare criteriu activ în snapshot-ul raportului.
4. Orice constatare AI are cel puțin un `SourceAnchor` cu document, pagină și pasaj.
5. Nicio ieșire AI nu este decizie finală.
6. Orice `UserDecision` indică autorul, momentul, acțiunea și revizia validării asupra căreia s-a decis.
7. Istoricul rapoartelor și al deciziilor este append-only din perspectiva domeniului.
8. Un raport cu perioada după `monitoringEndDate` nu poate intra în fluxul normal fără o justificare explicită.

## 6. Cerințe nefuncționale

- **Auditabilitate:** fiecare rezultat poate fi urmărit până la raport, criteriu, document și pasaj.
- **Confidențialitate:** datele beneficiarului nu sunt incluse în loguri, exemple, fixture-uri sau documentația repository-ului.
- **Configurabilitate:** numele modelului și adresa serviciului AI sunt configurabile în mediu.
- **Separarea componentelor:** UI-ul folosește exclusiv API-ul; API-ul folosește repository interfaces și `AIClient`.
- **Portabilitate DB:** SQLite este implementarea inițială; PostgreSQL poate fi adăugat fără schimbarea contractului de domeniu.
- **Rezistență:** un `AnalysisJob` poate fi reluat în siguranță și nu dublează validări prin retry accidental.

## 7. În afara scopului curent

- decizii juridice autonome;
- acces direct UI -> DB sau UI -> Qwen;
- publicarea documentelor beneficiarului;
- înlocuirea task-urilor, priorităților, distribuirii, validării, autorizării sau clarificărilor oficiale din MyADR/MySMIS;
- schimbarea implementării existente din `DAO/` și `DataBase/` în acest branch;
- migrarea efectivă de la SQLite la PostgreSQL.

## 8. Criterii de acceptare ale contextului de proiect

- Toți termenii canonici sunt definiți și folosiți consecvent.
- Perioada de monitorizare folosește `monitoringEndDate`, data contractuală explicită.
- Modelul descrie validări separate per raport și criteriu.
- Contractul AI refuză constatări fără document, pagină și pasaj.
- Responsabilitatea deciziei finale este atribuită utilizatorului.
- Limitele UI/API/repository/AIClient și responsabilitățile echipei sunt explicite.
- Contradicțiile din surse sunt înregistrate în `docs/source-index.md`.
