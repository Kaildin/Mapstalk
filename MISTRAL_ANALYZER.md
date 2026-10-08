# Mistral Website Relevance Analyzer

Modulo per l'analisi di pertinenza dei siti web utilizzando l'API di Mistral con il modello più economico (`mistral-tiny`).

## Descrizione

Questo modulo consente di analizzare il contenuto di siti web per determinare se sono pertinenti a una specifica nicchia di mercato, utilizzando l'intelligenza artificiale di Mistral per un'analisi semantica più accurata rispetto al semplice matching di keyword.

## Caratteristiche principali

- **Modello economico**: Utilizza `mistral-tiny` (il modello più economico di Mistral)
- **Chiamate asincrone**: Supporto completo per l'elaborazione asincrona con `aiohttp`
- **Estruzione HTML**: Scaricamento e pulizia automatica del contenuto HTML
- **Troncamento intelligente**: Tronca il contenuto a una lunghezza configurabile per risparmiare sui token
- **Batch processing**: Analisi parallela di più siti web contemporaneamente
- **Rate limiting**: Supporto per evitare di superare i limiti dell'API
- **Multi-industry**: Supporto per diverse nicchie (fotovoltaico, idraulico, ecc.)

## Installazione

```bash
# Assicurati che aiohttp sia installato
pip install aiohttp>=3.8.0
```

## Uso

### 1. Analisi singolo sito web (sincrono)

```python
from src.mistral_analyzer import MistralWebsiteAnalyzer

analyzer = MistralWebsiteAnalyzer(
    api_key="your-mistral-api-key",
    industry="fotovoltaico",
    model="mistral-tiny",  # Modello più economico
    max_content_length=10000,  # Tronca contenuto a 10k caratteri
    rate_limit_delay=0.1  # Attesa tra le chiamate API
)

result = analyzer.analyze_website("https://www.example-solar.it")

print(f"Pertinenza: {result.is_relevant}")
print(f"Categoria: {result.category}")
print(f"Confidenza: {result.confidence:.2%}")
print(f"Token usati: {result.tokens_used}")
```

### 2. Analisi multipla siti web (asincrona)

```python
import asyncio
from src.mistral_analyzer import MistralWebsiteAnalyzer

async def analyze_multiple():
    analyzer = MistralWebsiteAnalyzer(
        api_key="your-mistral-api-key",
        industry="idraulico"
    )
    
    urls = [
        "https://idraulico-rossi.it",
        "https://pronto-idraulico-milano.it",
        "https://example-plumber.com"
    ]
    
    results = await analyzer.analyze_websites_async(urls, max_concurrent=5)
    
    for result in results:
        print(f"{result.url}: {result.is_relevant} ({result.confidence:.2%})")

asyncio.run(analyze_multiple())
```

### 3. Funzione di convenienza per analisi singola

```python
import asyncio
from src.mistral_analyzer import analyze_website_relevance

async def quick_test():
    result = await analyze_website_relevance(
        api_key="your-mistral-api-key",
        url="https://www.solar-installer.it",
        industry="fotovoltaico"
    )
    print(result.is_relevant)

asyncio.run(quick_test())
```

### 4. Integrazione con enrich_existing.py

Puoi usare Mistral API direttamente con lo script di arricchimento:

```bash
# Con chiave API come variabile d'ambiente
MISTRAL_API_KEY="your-api-key" python enrich_existing.py \
    --input output/aziende_esistenti.csv \
    --output output/aziende_arricchite.csv \
    --industry fotovoltaico \
    --use-mistral

# Oppure con chiave API come parametro
python enrich_existing.py \
    --input output/aziende_esistenti.csv \
    --output output/aziende_arricchite.csv \
    --industry fotovoltaico \
    --use-mistral \
    --mistral-api-key "your-api-key"
```

## Test

### Esecuzione test interattivo

```bash
# Imposta la chiave API
MISTRAL_API_KEY="your-api-key" python test_mistral_analyzer.py

# Oppure con parametri
python test_mistral_analyzer.py --industry fotovoltaico --urls https://site1.com https://site2.com
```

### Test batch

```bash
# Crea un file con gli URL (uno per riga)
echo "https://site1.com" > urls.txt
echo "https://site2.com" >> urls.txt

# Esegui l'analisi batch
MISTRAL_API_KEY="your-api-key" python test_mistral_analyzer.py \
    --batch \
    --urls-file urls.txt \
    --output results.json
```

## Configurazione

### Parametri principali

| Parametro | Default | Descrizione |
|-----------|---------|-------------|
| `api_key` | - | **Obbligatorio**: Chiave API Mistral |
| `industry` | `fotovoltaico` | Nicchia di mercato per l'analisi |
| `model` | `mistral-tiny` | Modello Mistral da usare |
| `max_content_length` | `15000` | Lunghezza massima contenuto HTML |
| `timeout` | `30` | Timeout per le richieste HTTP |
| `max_retries` | `3` | Tentativi massimi per le chiamate API |
| `rate_limit_delay` | `0.1` | Attesa tra le chiamate API (secondi) |
| `language` | `italian` | Lingua per i prompt (italian/english) |

### Modelli Mistral disponibili

I modelli sono ordinati per costo (dal più economico al più costoso):

1. `mistral-tiny` - **Raccomandato per questo uso** - Più economico, veloce
2. `mistral-small` - Qualità leggermente migliore, costo leggermente più alto
3. `mistral-medium` - Qualità migliore, costo più alto
4. `mistral-large` - Qualità migliore, costo più alto
5. `open-mistral-7b` - Open source, buona qualità
6. `open-mixtral-8x7b` - Open source, qualità migliore

## Costi

### Prezzi Mistral (aprile 2024)

- **mistral-tiny**: ~$0.25 per milione di token
- **mistral-small**: ~$0.70 per milione di token
- **mistral-medium**: ~$2.00 per milione di token

### Ottimizzazione dei costi

Questo modulo include diverse ottimizzazioni per ridurre i costi:

1. **Troncamento del contenuto**: Solo i primi 15.000 caratteri vengono analizzati
2. **Pulizia HTML**: Rimozione di script, stili e altri contenuti non rilevanti
3. **Temperature bassa**: Impostata a 0.2 per risultati più deterministici
4. **Formato JSON**: Richiesta di output in JSON per parsing più semplice
5. **Elaborazione asincrona**: Più siti analizzati in parallelo per ridurre il tempo totale

## Esempi pratici

### Analisi di un elenco di siti

```python
import asyncio
from src.mistral_analyzer import MistralWebsiteAnalyzer

urls = [
    "https://solar-company-1.it",
    "https://solar-company-2.it", 
    "https://not-solar-company.it",
    "https://another-solar.it"
]

async def main():
    analyzer = MistralWebsiteAnalyzer(
        api_key="your-api-key",
        industry="fotovoltaico",
        model="mistral-tiny",
        max_concurrent=3  # 3 analisi simultanee
    )
    
    results = await analyzer.analyze_websites_async(urls)
    
    # Statistiche
    relevant = [r for r in results if r.is_relevant]
    print(f"Siti pertinenti: {len(relevant)}/{len(results)}")
    
    total_tokens = sum(r.tokens_used or 0 for r in results)
    print(f"Token totali: {total_tokens}")
    
    # Costo stimato (mistral-tiny: $0.25 per milione di token)
    cost_per_million = 0.25
    estimated_cost = (total_tokens / 1000000) * cost_per_million
    print(f"Costo stimato: ${estimated_cost:.4f}")

asyncio.run(main())
```

## Risoluzione problemi

### Errore: "Mistral API key is required"

Assicurati di:
1. Passare la chiave API come parametro
2. Oppure impostare la variabile d'ambiente `MISTRAL_API_KEY`

### Errore: "Rate limited"

Aumenta `rate_limit_delay`:
```python
analyzer = MistralWebsiteAnalyzer(
    api_key="your-key",
    rate_limit_delay=1.0  # Attende 1 secondo tra le chiamate
)
```

### Errore: "Max retries exceeded"

Aumenta `max_retries`:
```python
analyzer = MistralWebsiteAnalyzer(
    api_key="your-key",
    max_retries=5
)
```

## Contribuzioni

Per suggerimenti o problemi, apri una issue su GitHub o contribuisci direttamente con una pull request.

## Licenza

Stessa licenza del progetto principale (vedi README.md).
