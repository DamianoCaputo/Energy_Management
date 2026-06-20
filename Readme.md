# Energy Management Optimization System

## Descrizione del Progetto

Sistema completo di ottimizzazione della gestione energetica per un edificio (complesso universitario) dotato di fonti rinnovabili, accumulo in batteria, generatore diesel e collegamento alla rete elettrica.

Il progetto analizza dati di carico energetico, radiazione solare, velocità del vento e temperatura esterna per ottimizzare la **gestione del dispatch energetico**, minimizzando i costi operativi considerando diversi scenari di prezzo del carburante.

### Obiettivi Principali
- Ottimizzazione economica del dispatch energetico
- Gestione intelligente della batteria di accumulo
- Valutazione di scenari di costo del carburante
- Analisi della qualità dei dati
- Generazione di report e visualizzazioni

---

## Struttura del Progetto

```
Energy_Management/
├── main.py                          # Script principale della pipeline
├── requirements.txt                 # Dipendenze Python
├── Readme.md                        # Questo file
│
├── src/                             # Moduli principali
│   ├── __init__.py
│   ├── config.py                    # Configurazioni asset e tariffe
│   ├── reader.py                    # Lettura e caricamento dati
│   ├── cleaning.py                  # Normalizzazione e aggregazione dati
│   ├── analysis.py                  # Ottimizzazione del dispatch
│   ├── plotting.py                  # Generazione grafici
│   └── utils.py                     # Funzioni utility
│
├── data/
│   ├── raw/                         # Dati grezzi (formato .mat MATLAB)
│   │   ├── buildings_load.mat       # Carichi edifici
│   │   ├── office_load.mat          # Carichi ufficio
│   │   ├── Ir_rome_campus_bio_medico_2022.mat  # Radiazione solare
│   │   ├── T_ex_rome_campus_bio_medico_2022.mat  # Temperatura esterna
│   │   ├── PUN_2022.mat             # Prezzo unico nazionale energia
│   │   └── res_1_year_pu.mat        # Generazione rinnovabile (PV+vento)
│   │
│   └── processed/                   # Dati normalizzati (CSV)
│       ├── buildings_load_pul.csv
│       ├── office_load_pul.csv
│       ├── pun_2022_pun.csv
│       ├── t_ex_rome_campus_bio_medico_2022_t_ex.csv
│       ├── res_1_year_pu_p_pv.csv
│       ├── res_1_year_pu_p_w.csv
│       └── ir_rome_campus_bio_medico_2022_ir.csv
│
├── outputs/                         # Output della pipeline
│   ├── pipeline.log                 # Log di esecuzione
│   ├── data_quality_report.csv      # Rapporto qualità dati
│   ├── normalized_timeseries.csv    # Serie temporale normalizzata
│   ├── dispatch_fuel_0_45.csv       # Dispatch ottimale (fuel cost €0.45/kWh)
│   ├── dispatch_fuel_0_6.csv        # Dispatch ottimale (fuel cost €0.60/kWh)
│   ├── summary.csv                  # Riepilogo risultati
│   └── plots/                       # Grafici per ogni scenario
│       ├── fuel_0_45/               # Grafici scenario 1
│       └── fuel_0_6/                # Grafici scenario 2
│
└── tests/                           # Test unitari
    ├── test_reader.py
    └── __pycache__/
```

---

## Installazione e Setup

### Prerequisiti
- Python 3.10+
- pip

### Installazione
```bash
cd Energy_Management
pip install -r requirements.txt
```

---

## Utilizzo

```bash
python main.py [options]
```

**Argomenti disponibili:**

| Argomento | Default | Descrizione |
|-----------|---------|-------------|
| `--data` | `data/raw` | Cartella o file dati grezzi di input |
| `--processed` | `data/processed` | Cartella dati CSV normalizzati |
| `--refresh-processed` | - | Forza ricaricamento da raw e sovrascrive CSV |
| `--no-processed-cache` | - | Disabilita cache CSV, legge sempre da raw |
| `--out` | `outputs` | Cartella output risultati |
| `--plots` | `<out>/plots` | Cartella per i grafici |
| `--fuel-cost` | `[0.45, 0.60]` | Scenari costo carburante [€/kWh] |
| `--use-forecast` | - | Usa colonne forecasted invece di actual |
| `--chunk-hours` | `168` | Dimensione chunk ottimizzazione (ore) |
| `--run-all` | - | Esegui pipeline completa |

---

## Moduli Principali

### 1. **config.py** - Configurazione
Definisce i parametri dell'impianto e le tariffe di energia.

**AssetConfig:** Parametri dell'asset
```python
- pv_nom_kw: 40 kW (potenza nominale FV)
- wind_nom_kw: 60 kW (potenza nominale eolico)
- office_nom_kw: 180 kW (carico ufficio max)
- battery_power_kw: 130 kW (potenza batteria)
- battery_capacity_kwh: 130 kWh (capacità batteria)
- battery_eta_charge/discharge: 0.95 (efficienze 95%)
- soc_min/max: 0.10-0.90 (stato di carica 10%-90%)
- soc_initial: 0.50 (stato iniziale 50%)
- generator_power_max_kw: 70 kW
- generator_power_min_kw: 20 kW (tecnico minimo)
- generator_eta: 0.60 (efficienza 60%)
- grid_import_max_kw: 200 kW
- grid_export_max_kw: 100 kW
```

**TariffConfig:** Tariffe di energia (multi-fascia)
```python
- f1_eur_kwh: 0.53276 €/kWh (fascia 1 - orari di punta)
- f2_eur_kwh: 0.54858 €/kWh (fascia 2 - mezza fascia)
- f3_eur_kwh: 0.46868 €/kWh (fascia 3 - fuori punta)
```

### 2. **reader.py** - Lettura Dati
Carica dati da molteplici formati (.mat, .csv, .xlsx, .json, .tsv).

**Funzioni principali:**
- `load_dataset()` - Carica da raw o cache CSV processati
- `validate_schema()` - Valida coerenza campi
- Supporta fallback automático tra codifiche (UTF-8, Latin-1, CP1252)

**Formati supportati:**
- `.mat` - MATLAB (variabili come DataFrames)
- `.csv/.tsv` - Testo delimitato
- `.xlsx/.xls` - Excel (una DF per sheet)
- `.json` - JSON standard o line-delimited

### 3. **cleaning.py** - Normalizzazione Dati
Aggrega i dati grezzi in una serie temporale unica e normalizzata.

**Funzione principale: `build_project_timeseries()`**

Processa:
1. **Carichi:** ufficio + residenziale
2. **Generazione rinnovabile:** PV + eolico
3. **Prezzo importazione:** da PUN (Prezzo Unico Nazionale) con fascie orarie
4. **Prezzo esportazione:** secondo regole di mercato
5. **Dati ambientali:** radiazione solare, temperatura

Output: DataFrame orario con colonne:
```
timestamp, office_load_kwh, renewable_kw, import_price_eur_kwh, 
export_price_eur_kwh, temperature_c, solar_irradiance, ...
```

### 4. **analysis.py** - Ottimizzazione Dispatch
Risolve problema di ottimizzazione lineare per minimizzare costi energetici.

**Funzione: `optimize_dispatch()`**

**Variabili decisionali:**
- `p_import` - Potenza importata dalla rete [kW]
- `p_export` - Potenza esportata verso rete [kW]
- `p_gen` - Potenza generatore diesel [kW]
- `p_charge` - Potenza ricarica batteria [kW]
- `p_discharge` - Potenza scarica batteria [kW]
- `p_curtail` - Curtailment fonti rinnovabili [kW]
- `p_pev` - Carica auto elettrica [kW]
- `soc` - Stato di carica batteria [kWh]

**Vincoli:**
- Bilancio potenza: richiesta = fonti + importazione - esportazione
- Limiti generatore: potenza minima/massima
- Limiti batteria: SoC tra 10%-90%, potenza carica/scarica
- Limiti rete: import/export max
- PEV: carica giornaliera 30 kWh con efficiencia 90%

**Obiettivo:** Minimizzare costo totale
```
cost = Σ(p_import × import_price - p_export × export_price + p_gen × fuel_cost)
```

**Metodo:** `scipy.optimize.linprog()` (algoritmo simplex duale)

**Funzione: `summarize_dispatch()`**
Calcola KPI da risultati:
- Costi annuali per scenario
- Uso generatore e batteria
- Bilanciamento importazione/esportazione

### 5. **plotting.py** - Visualizzazioni
Genera grafici per analisi risultati.

**Grafici generati:**
1. **soc_year.png** - Stato di carica batteria annuale
2. **power_profiles_week.png** - Profili potenza prima settimana
3. **daily_cost.png** - Costo giornaliero annuale

### 6. **utils.py** - Funzioni di Supporto
Funzioni helper e utility:
- `setup_logging()` - Configura logging
- `ensure_dir()` - Crea cartelle se non esistono
- `dataframe_quality_report()` - Report qualità dati (valori mancanti, etc.)
- `normalize_columns()` - Normalizza nomi colonne

---

## Flusso della Pipeline

```
1. CARICAMENTO DATI
   ├─ Leggi raw (.mat, .csv, etc.) o cache CSV
   ├─ Valida schema
   └─ Genera quality report

2. NORMALIZZAZIONE
   ├─ Aggrega carichi (office + residenziale)
   ├─ Aggrega generazione (PV + eolico)
   ├─ Calcola tariffe importazione multi-fascia
   ├─ Sincronizza timestamp
   └─ Output: normalized_timeseries.csv

3. OTTIMIZZAZIONE (per ogni scenario di fuel_cost)
   ├─ Dividi in chunk (default 168 ore = settimane)
   ├─ Per ogni chunk:
   │  ├─ Risolvi problema LP (linprog)
   │  ├─ Aggiorna SoC batteria per chunk successivo
   │  └─ Salva risultati parziali
   └─ Output: dispatch_fuel_X_XX.csv

4. ANALISI RISULTATI
   ├─ Calcola KPI per scenario
   ├─ Genera summary.csv
   └─ Output: summary.csv

5. VISUALIZZAZIONE
   ├─ Plot SoC annuale
   ├─ Plot profili potenza prima settimana
   ├─ Plot costi giornalieri
   └─ Output: plots/fuel_X_XX/*.png

6. LOGGING
   └─ Tutte le operazioni registrate in outputs/pipeline.log
```

---

## Output e Risultati

### File Output Principali

**1. `normalized_timeseries.csv`**
- Una riga per ogni ora dell'anno (8760 righe)
- Colonne: timestamp, carichi, generazione, prezzi, dati meteorologici

**2. `dispatch_fuel_X_XX.csv`**
- Risultati ottimizzazione per ogni scenario
- Colonne: p_import, p_export, p_gen, p_charge, p_discharge, soc_pct, costo, etc.

**3. `summary.csv`**
- Una riga per scenario
- KPI: costo totale, ore generatore, uso batteria, etc.

**4. `data_quality_report.csv`**
- Analisi qualità per ogni dataset: valori mancanti, type, dimensioni

### Cartella `plots/`
Grafici PNG per ogni scenario:
- `soc_year.png` - Stato carica batteria
- `power_profiles_week.png` - Profili settimana
- `daily_cost.png` - Costi giornalieri

---

## Interpretazione Risultati

### State of Charge (SoC)
- Grafico `soc_year.png` mostra quando batteria è carica/scarica
- Picchi: accumulazione da fonti rinnovabili
- Valli: scariche durante carichi alti

### Power Profiles (Prima settimana)
- **Office Load**: carico dell'edificio (picco 8-19h)
- **Renewable Generation**: produzione solare (picco 12-14h)
- **Grid Import**: acquisto dalla rete
- **Grid Export**: vendita alla rete
- **DG**: generatore diesel (quando economicamente conveniente)

### Daily Cost
- Costi giornalieri di gestione
- Effetto delle tariffe multi-fascia
- Impatto di fuel_cost su strategie


