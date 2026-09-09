# 🚐 Poradnik Uruchomienia Aplikacji VW California Trip Planner na Windows

Ten przewodnik przeprowadzi Cię przez proces uruchomienia aplikacji na Twoim komputerze z systemem Windows (10 lub 11) krok po kroku.

---

## 📋 Co będzie nam potrzebne?

Zanim zaczniemy, upewnij się, że masz połączenie z internetem. Pobierzemy 3 darmowe programy:
1. **Python** – język, w którym napisana jest aplikacja.
2. **Docker Desktop** – program, który jednym kliknięciem uruchomi bazę danych z mapami.
3. **Pobraną aplikację** z serwisu GitHub.

---

## KROK 1: Pobranie plików aplikacji na Twój komputer

1. Wejdź na stronę projektu na GitHubie w swojej przeglądarce.
2. Kliknij zielony przycisk **`<> Code`** (znajdziesz go po prawej stronie na górze).
3. Wybierz opcję **`Download ZIP`**.
4. Po pobraniu pliku `VW-main.zip` Otwórz folder **Pobrane** (Downloads).
5. Kliknij na plik ZIP prawym przyciskiem myszy i wybierz **Wyodrębnij wszystkie...** (Extract All).
6. Jako docelowe miejsce wybierz np. Twój pulpit lub dysk `C:\` (np. `C:\VW`).

---

## KROK 2: Instalacja języka Python

Aplikacja wymaga Pythona do działania.

1. Wejdź na stronę [python.org/downloads](https://www.python.org/downloads/).
2. Kliknij duży żółty przycisk **Download Python 3.11** (lub nowszy, np. 3.12).
3. Otwórz pobrany plik instalacyjny (`python-3.x.x-amd64.exe`).
4. ⚠️ **BARDZO WAŻNE (NAJCZĘSTSZY BŁĄD):**
   Na samym dole pierwszego okienka instalatora **ZAZNACZ PTASZEK**:
   `[X] Add python.exe to PATH` (Dodaj python.exe do zmiennej środowiskowej PATH).
5. Kliknij **Install Now** i poczekaj na zakończenie instalacji.
6. Zamknij instalator przyciskiem **Close**.

---

## KROK 3: Instalacja i uruchomienie bazy danych (Docker Desktop)

Nasza aplikacja potrzebuje bazy danych z obsługą map (PostGIS). Najprostszym sposobem na jej uruchomienie bez skomplikowanej konfiguracji jest użycie darmowego programu **Docker Desktop**.

1. Wejdź na stronę [docker.com/products/docker-desktop](https://www.docker.com/products/docker-desktop/).
2. Kliknij **Download for Windows**.
3. Zainstaluj program (klikaj *Next/OK* przy domyślnych ustawieniach). Po instalacji komputer może poprosić o ponowne uruchomienie (Restart).
4. Po ponownym uruchomieniu komputera **włącz program Docker Desktop** (znajdziesz go w menu Start).
5. Zaakceptuj regulamin i poczekaj chwilę, aż ikona Dockera na pasku zadań (koło zegarka) przestanie się kręcić i pojawi się status *Engine Running* (zielona ikona).

---

## KROK 4: Otwarcie terminala (PowerShell) w folderze projektu

1. Otwórz folder z rozpakowaną aplikacją (ten, w którym znajdują się pliki takie jak `main.py`, `README.md`, `requirements.txt`).
2. Kliknij w puste miejsce w pasku adresu eksploratora plików u góry okna, wpisz: `powershell` i naciśnij **Enter**.
3. Otworzy się niebieskie okno konsoli (Program PowerShell) z gotową ścieżką do Twojego folderu.

---

## KROK 5: Utworzenie środowiska i instalacja bibliotek

W otwartym oknie PowerShell wpisuj po kolei poniższe polecenia (po każdym naciśnij **Enter**):

### 1. Zezwolenie na uruchamianie skryptów w PowerShell (jednorazowo):
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process
```
*(Gdy konsola zapyta o potwierdzenie, wpisz litery `T` lub `Y` i naciśnij Enter).*

### 2. Utworzenie wirtualnego środowiska:
```powershell
python -m venv .venv
```

### 3. Aktywacja środowiska:
```powershell
.\.venv\Scripts\Activate.ps1
```
*(Na początku linii pojawi się zielony napis `(.venv)` – oznacza to, że środowisko jest aktywne).*

### 4. Instalacja wymaganych bibliotek:
```powershell
pip install -r requirements.txt
```
Poczekaj chwilę, aż pobiorą się i zainstalują wszystkie potrzebne moduły.

---

## KROK 6: Konfiguracja pliku ustawień (`.env`)

Aplikacja musi wiedzieć, jak połączyć się z bazą danych i z jakich kluczy API skorzystać.

1. W folderze z aplikacją kliknij prawym przyciskiem myszy w wolnym miejscu, wybierz **Nowy** ➔ **Dokument tekstowy**.
2. Nazwij ten plik dokładnie: `.env` (upewnij się, że nie nazywa się `.env.txt`).
3. Otwórz plik `.env` w programie **Notatnik** (Notepad).
4. Wklej poniższą treść:

```ini
# Klucze API (Wklej tutaj swoje klucze)
GEMINI_API_KEY=twój_klucz_gemini_lub_zostaw_puste
OPENAI_API_KEY=twój_klucz_openai_lub_zostaw_puste
GOOGLE_MAPS_API_KEY=twój_klucz_google_maps
GOOGLE_MAPS_KEY=twój_klucz_google_maps

# Ustawienia połączenia z bazą danych Docker
DB_URL=postgresql://postgres:DupaBlada2137?@localhost:5432/postgres

# Tajny klucz serwera
SECRET_KEY=vw_california_secret_key_2026
```

5. Zapisz plik (**Skrót: Ctrl + S**) i zamknij Notatnik.

> **Wskazówka dotycząca Kluczy API:**
> - Klucz **Gemini API** uzyskasz darmowo w 1 minutę na stronie: [aistudio.google.com](https://aistudio.google.com/)
> - Dokładny przewodnik krok po kroku, jak uzyskać i włączyć klucz **Google Maps API**, znajdziesz na samym dole tej instrukcji w rozdziale [🗺️ Konfiguracja Google Maps API w Google Cloud Platform](#-konfiguracja-google-maps-api-w-google-cloud-platform-gcp).

---

## KROK 7: Uruchomienie bazy danych i przygotowanie danych

W oknie PowerShell (tam, gdzie świeci się zielony napis `(.venv)`):

### 1. Włącz bazę danych w Dockerze:
```powershell
docker compose up -d
```
*(Pobierze się i uruchomi kontener z bazą PostgreSQL i PostGIS. Zobaczysz napis `Started` lub `Running`).*

### 2. Przygotuj bazy danych i wgraj wstępne kempingi:
```powershell
python apply_migration.py
```
*(Zobaczysz komunikat: `✨ Database setup complete.`)*

---

## KROK 8: Uruchomienie Aplikacji! 🚀

Wpisz ostatnią komendę w PowerShell:

```powershell
python -m tools.server
```

Zobaczysz w konsoli informację, że serwer wystartował.

### 🌐 Jak otworzyć aplikację w przeglądarce?
1. Otwórz swoją przeglądarkę internetową (Chrome, Edge lub Firefox).
2. W pasku adresu wpisz:
   **`http://localhost:5050`** (lub `http://127.0.0.1:5050`)
3. Naciśnij **Enter**.

**Gratulacje! 🚐** Zobaczysz interaktywny pulpit nawigacyjny aplikacji VW California Trip Planner.

---

## 🔄 Jak uruchomić aplikację następnym razem?

Gdy wyłączysz komputer i zechcesz uruchomić aplikację ponownie innego dnia:

1. Włącz program **Docker Desktop**.
2. Otwórz folder z aplikacją i uruchom **PowerShell**.
3. Wpisz 3 krótkie komendy:
   ```powershell
   .\.venv\Scripts\Activate.ps1
   docker compose up -d
   python -m tools.server
   ```
4. Otwórz w przeglądarce stronę `http://localhost:5050`.

---

## 🛠️ Najczęstsze problemy i ich rozwiązania

| Problem | Wyjaśnienie i Rozwiązanie |
| :--- | :--- |
| **`python` nie jest rozpoznawana jako polecenie...** | Zapomniano zaznaczyć ptaszka `Add python.exe to PATH` podczas instalacji Pythona. Odinstaluj Pythona, zainstaluj go ponownie i **koniecznie zaznacz ten ptaszek** na pierwszym ekranie! |
| **Nie można wczytać pliku Activate.ps1...** | Wpisz w PowerShell komendę: `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process` i wpisz `T`, a następnie spróbuj ponownie z aktywacją. |
| **Błąd połączenia z bazą danych (Database connection error)** | Upewnij się, że program **Docker Desktop** jest włączony i działa (zielona ikona), a potem wpisz `docker compose up -d`. |
| **Jak zatrzymać aplikację w PowerShell?** | Kliknij w okno PowerShell i naciśnij skrót **Ctrl + C**. |

---

## 🗺️ Konfiguracja Google Maps API w Google Cloud Platform (GCP)

Aplikacja potrzebuje klucza Google Maps do 4 rzeczy:
- wyświetlania interaktywnej mapy na stronie,
- wyszukiwania kempingów i atrakcji (POI),
- zamiany nazw miast na współrzędne geograficzne (geokodowanie),
- wyliczania tras przejazdu kamperem.

Poniżej znajduje się instrukcja, jak założyć i skonfigurować klucz krok po kroku.

---

### Krok 1: Zaloguj się do Google Cloud Console
1. Wejdź na stronę: [console.cloud.google.com](https://console.cloud.google.com/).
2. Zaloguj się swoim zwykłym kontem Google (np. tym samym, którego używasz do Gmaila).
3. Zaakceptuj warunki korzystania z platformy, jeśli logujesz się tam po raz pierwszy.

---

### Krok 2: Utwórz nowy projekt
1. W lewym górnym rogu ekranu (zaraz obok logo **Google Cloud**) kliknij rozwijaną listę projektów.
2. W okienku, które się pojawi, kliknij przycisk **`NEW PROJECT`** (Nowy projekt) w prawym górnym rogu.
3. W polu **Project name** wpisz dowolną nazwę, np.: `VW-California-Planner`.
4. Kliknij niebieski przycisk **`CREATE`** (Utwórz).
5. Poczekaj 5-10 sekund, a następnie w powiadomieniu (ikona dzwonka w prawym górnym rogu) lub z listy u góry **kliknij i wybierz nowo utworzony projekt**, aby był aktywny.

---

### Krok 3: Podpięcie konta rozliczeniowego (Billing)
Google wymaga podpięcia karty płatniczej do konta Cloud w celu weryfikacji tożsamości.
> 💡 **Czy to jest płatne?**
> Google daje każdemu użytkownikowi **darmowy kredyt w wysokości 200 $ każdego miesiąca** na usługi Google Maps Platform.
> Do prywatnych testów i korzystania z aplikacji zużyjesz zaledwie ułamek procenta tej kwoty. Nie zostaną pobrane żadne opłaty, dopóki nie przekroczysz tego ogromnego darmowego limitu.

1. W lewym menu nawigacyjnym (ikona ☰) wybierz **Billing** (Płatności).
2. Kliknij **Link a billing account** / **Manage billing accounts** i dodaj swoją kartę, postępując zgodnie z instrukcjami na ekranie.

---

### Krok 4: Włączenie wymaganych bibliotek API (Enable APIs)
Aplikacja korzysta z 4 konkretnych usług Google Maps. Musimy je włączyć w naszym projekcie:

1. W menu bocznym (☰) przejdź do: **APIs & Services** (Interfejsy API i usługi) ➔ **Library** (Biblioteka) — lub po prostu wpisz **Library** w głównym pasku wyszukiwania na samej górze.
2. Wyszukaj i włącz po kolei poniższe **4 usługi** (wpisz nazwę w wyszukiwarkę, kliknij kafelek z wynikiem, a następnie naciśnij niebieski przycisk **`ENABLE`** / **Włącz**):
   - **`Maps JavaScript API`** *(odpowiada za wyświetlanie mapy w przeglądarce)*
   - **`Places API`** oraz **`Places API (New)`** *(odpowiada za wyszukiwanie kempingów i punktów POI)*
   - **`Geocoding API`** *(odpowiada za rozpoznawanie nazw miast i współrzędnych)*
   - **`Routes API`** oraz **`Directions API`** *(odpowiada za wyliczanie tras podróży)*

---

### Krok 5: Wygenerowanie klucza API (API Key)
Gdy usługi są już włączone:

1. W menu bocznym przejdź do: **APIs & Services** ➔ **Credentials** (Dane logowania).
2. Na samej górze kliknij przycisk **`+ CREATE CREDENTIALS`** (Utwórz dane logowania).
3. Z listy wybierz **`API key`** (Klucz interfejsu API).
4. Google w kilka sekund wygeneruje klucz. Zobaczysz okienko:
   `API key created`
   oraz ciąg znaków zaczynający się od `AIzaSy...`.
5. Kliknij ikonkę **Kopiuj** obok klucza.

---

### Krok 6: Ograniczenie klucza (Zalecane ze względów bezpieczeństwa)
W tym samym okienku (lub klikając ikonę ołówka obok klucza):
1. W sekcji **API restrictions** wybierz opcję **`Restrict key`** (Ogranicz klucz).
2. Z rozwijanej listy zaznacz tylko te interfejsy, które włączyliśmy:
   - *Maps JavaScript API*
   - *Places API*
   - *Geocoding API*
   - *Routes API* / *Directions API*
3. Kliknij **Save** (Zapisz).

---

### Krok 7: Wklejenie klucza do pliku `.env` w projekcie
1. Otwórz plik `.env` w folderze projektu za pomocą **Notatnika**.
2. Wklej swój wygenerowany klucz w wierszach:
   ```ini
   GOOGLE_MAPS_API_KEY=AIzaSyTwójWygenerowanyKluczTutaj
   GOOGLE_MAPS_KEY=AIzaSyTwójWygenerowanyKluczTutaj
   ```
3. Zapisz plik (**Ctrl + S**).

---

### Krok 8: Jak sprawdzić, czy klucz działa poprawnie?
W oknie PowerShell w folderze projektu wpisz komendę testującą:

```powershell
python -m tools.verify_connections
```

Powinieneś zobaczyć zielony komunikat:
```text
✅ Google Maps: connected (Wolfsburg lat=52.42..., lng=10.78...)
```
Oznacza to, że Google Maps Platform jest w pełni skonfigurowane i gotowe do podróży! 🚐🗺️
