# Italia in comune — @italia_incomune

Account Instagram automatico che racconta l'Italia comune per comune: classifiche, mappe, storie, cibo.
Tutto gira da solo con GitHub Actions: ogni giorno genera e pubblica un contenuto, ogni mezz'ora risponde
ai commenti che contengono il nome di un comune mandando la sua scheda.

## Calendario

| Giorno | Formato |
|---|---|
| Lunedì | Reel: conto alla rovescia di una classifica |
| Martedì | Carosello: storia di un comune (`contenuti/storie.json`) |
| Mercoledì | Reel: il comune del giorno |
| Giovedì | Carosello: classifica con una slide per comune |
| Venerdì | Reel: sfida «Chi è più grande?» |
| Sabato | Carosello: il comune e il suo piatto (`contenuti/cibo.json`) |
| Domenica | Reel: mappa che si riempie |

Quando storie o piatti finiscono, il giorno passa in automatico a un altro formato.
Per aggiungerne basta modificare i due file JSON nella cartella `contenuti`.

## Comandi (scheda Actions → Italia in comune → Run workflow)

- **verifica**: controlla che token e account funzionino. Non pubblica niente.
- **anteprima**: genera i contenuti dei prossimi 7 giorni e li salva come file scaricabile («Artifacts»). Non pubblica niente.
- **lancio**: da usare una volta sola all'avvio. Pubblica 6 contenuti per riempire il profilo.
- **pubblica** / **commenti**: le stesse azioni che partono da sole ogni giorno e ogni mezz'ora.

## Secrets (Settings → Secrets and variables → Actions)

- `IG_TOKEN` (obbligatorio): il token generato su Meta for Developers.
- `IG_USER_ID`, `GRAPH_HOST` (facoltativi): servono solo se la verifica non trova l'account da sola.

## Note

- Il repository deve essere **pubblico**: Instagram scarica le immagini dei caroselli da un link pubblico.
  Il token resta nei Secrets, cifrato e invisibile a chiunque.
- La popolazione dei comuni viene dal censimento ISTAT 2011 ed è indicata così in ogni grafica.
- Fonti dei dati: ISTAT tramite comuni-json, confini comunali openpolis.
