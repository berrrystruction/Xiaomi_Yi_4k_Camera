# Passaggio di consegne – progetto Yi 4K (contesto per un altro assistente)

Questo documento riassume una lunga conversazione tra l'utente e un assistente AI
(Claude) sul riuso di una action cam **Yi 4K** tramite questo repository. Serve a
riprendere il lavoro senza ripartire da zero. Lingua dell'utente: **italiano**.

---

## 1. Obiettivo dell'utente

L'utente ha fatto un fork del vecchio repository di `irungentoo`
(`Xiaomi_Yi_4k_Camera`) e vuole tornare a usare la camera, sfruttando e
ampliando le mod. Interessi espressi, in ordine:

1. capire se il codice del repo è affidabile o pericoloso;
2. estendere le capacità della camera (bitrate, risoluzioni, funzioni di altre camere);
3. **vedere lo stream della camera in rete locale con VLC** ← punto aperto attuale.

## 2. Dati certi sulla camera

| Voce | Valore |
|---|---|
| Modello | **Yi 4K Action Camera** (non 4K+); codice interno Z16 |
| Firmware | **1.10.99 Build 2748r** (più recente dell'ultimo supportato dal repo, 1.10.9) |
| Orologio | sbagliato (data 2014), l'utente deve reimpostarlo: ignorare le date dei file |
| SD | Hephinov 64 GB U3 V30 A1 – **verificata con H2testw**: nessun errore, capacità reale, scrittura 33,2 MB/s, lettura 82,2 MB/s |
| PC dell'utente | Windows; usa SourceTree, VLC, Notepad++ |

## 3. Fatti tecnici stabiliti

- La camera ha un SoC Ambarella con RTOS + Linux. L'RTOS esegue all'avvio
  `autoexec.ash` dalla radice della SD (terminazioni di riga **Unix**, riga vuota finale).
- Le mod scrivono **solo in RAM** (`writel/writew`): togliendo `autoexec.ash`
  e riavviando la camera torna di fabbrica. Nessun rischio permanente.
- Gli indirizzi dipendono dalla versione firmware.
- **Firmware 1.10.99 = stessi indirizzi della 1.10.9**, verificato su un dump reale
  della camera (vedi §5). Tabella bitrate a `0xA06D48BC`, audio a `0xA06D4538`,
  tabella risoluzioni ultra a `0xA06DCFAC` (+`0x86F0` dal bitrate).
- La tabella bitrate è condivisa tra NTSC e PAL: `0xA06D48BC` vale sia per 4K 30P sia per 4K 25P.
- Per ogni modalità: indirizzo = qualità alta; +0x10 media; +0x20 bassa;
  +0x04 lower bound, +0x08 upper bound. Valori in float32 (120 = `0x42F00000`,
  150 = `0x43160000`).
- I file del video: `.MP4` = video vero; `.SEC` = copia a bassa risoluzione per
  l'anteprima dell'app; `.THM` = miniatura. `.SEC`/`.THM` si possono cancellare.
- La camera **divide i video a ~4 GB** (nomi `YDXJnnnn` → `YN01nnnn`, `YN02nnnn`…):
  è normale e continuo, non è un errore. Unione senza perdita: LosslessCut o
  `ffmpeg -f concat -safe 0 -i lista.txt -c copy out.mp4`.

## 4. Risultati dei test sulla camera reale

| Test | Esito |
|---|---|
| Dump 16 MB `savebin c:\dump.bin 0xA0000000 l 16777216` | **la camera si blocca all'avvio** (sbloccata togliendo la batteria e cancellando autoexec.ash) |
| Dump 2 MB `savebin c:\dump.bin 0xA0600000 l 2097152` | **ok**, usato per trovare gli indirizzi |
| Bitrate 4K 30P alta = 120 Mbps | **ok**: misurati ~121 Mbps, 15 min di registrazione continua senza interruzioni |
| Bitrate 4K 30P alta = 150 Mbps | **crash** della camera |

Diagnosi del crash a 150 Mbps (dal log RTOS `dsp.log`, ottenuto con `enable_logs`):
`HENC: henc_send_eng0_msg(1): ERROR! msg queue full ... num_of_fields_encoded_eng0=162, num_of_fields_encoded_henc=194`
seguito da `Assertion '0' at .../h264_enc/orccode/enc_thread/enc_th_main.c:5041 failed`.
Lo stadio ENG0 (scrittura del bitstream finale) dell'encoder H.264 non tiene il
passo, il buffer intermedio cresce da ~4 a ~18 MB su 32 MB finché la coda si
riempie. **Il limite è l'encoder, non la SD.** Decisione: **120 Mbps è il valore
scelto**; 130 possibile ma sconsigliato.

## 5. Cosa è stato aggiunto al repository

Branch: **`claude/modest-knuth-tvzwsv`** sul fork `berrrystruction/Xiaomi_Yi_4k_Camera`
(non ancora unito a `master`, nessuna pull request aperta).

| Commit | Contenuto |
|---|---|
| `e5e024c` | `tools/yi4k_port/find_addresses.py` + README: trova gli indirizzi delle mod in un dump RAM di un firmware nuovo e genera gli `autoexec.ash` |
| `4de4f8d` | dump consigliato ridotto a 2 MB a `0xA0600000`, opzione `--base`, istruzioni di sblocco |
| `99f1385` | cartelle `bitrate/4k/1.10.99/` e `4k/ultra_increased_resolution/1.10.99/`; scelta dell'audio corretto se ci sono più candidati |
| `ba39fad` | limiti testati documentati in `bitrate/4k/1.10.99/Readme.md` |
| `9402cb7` | `tools/live_view/live_view.py` + README: avvia lo stream RTSP di anteprima per VLC |

Come funziona `find_addresses.py`: in tutti i firmware 4K noti (1.8.9→1.10.9)
la tabella bitrate ha layout e valori di fabbrica identici e si sposta solo in
blocco; la tabella risoluzioni sta sempre a +0x86F0; l'audio 128 kb/s tra
-0x384 e -0x394. Lo strumento cerca la tabella, verifica tutti i 207 valori e
i valori di fabbrica delle risoluzioni (3840x2160, 1920x1080), e non genera
nulla se un controllo fallisce. Validato rigenerando esattamente gli script
del repo da dump simulati di 1.8.9, 1.9.0, 1.9.4, 1.10.4, 1.10.7.

`live_view.py`: protocollo JSON su TCP 7878 (msg_id 257 sessione/token, 259
con `param "none_force"` avvio viewfinder, 3 come keepalive ogni 10 s, 258
chiusura), parsing robusto di messaggi spezzati/concatenati. Stream atteso su
`rtsp://192.168.42.1/live`. **Testato solo contro una camera simulata**: il
protocollo deriva dalla conoscenza comune delle camere Yi, non dal repo, e
non è ancora stato verificato sulla camera reale.

## 6. Analisi del codice originale (problemi noti, non corretti)

- `firmware_unpacker/unpacker.c`: **stack buffer overflow** confermato con
  AddressSanitizer (`sprintf` in `char file_name[128]` con percorso di output
  lungo); nessuna validazione delle dimensioni negli header; `fread` non
  controllato; TODO sulla dimensione Z16 (`+7`).
- `camera_controller/controller.py`: `recv(1024)`+`json.loads` fragile con
  messaggi spezzati/multipli; non controlla le risposte a start/stop (lo stato
  `recording` può desincronizzarsi); `except: pass`; nessuna riconnessione.
  (`live_view.py` usa già un parser corretto riutilizzabile.)
- Sicurezza: `telnet/console_enable.script` apre una shell **root senza password**
  via Wi‑Fi; esempio `start.sh` (solo 4K+) con MAC fisso e password in chiaro;
  QR della modalità live con password Wi‑Fi in chiaro.
- Mod più rischiosa del repo: `4k+/increased_framerate` (overclock DSP/core e
  patch di istruzioni) – non applicabile alla 4K.
- Verificato: in tutte le versioni bitrate gli indirizzi corrispondono alle
  tabelle e i commenti in Mbps ai float; nessun file con CRLF.

## 7. Stato attuale e punti aperti

1. **[IN CORSO] Collegamento del PC al Wi‑Fi della camera.** L'utente vede la
   rete ma Windows sembra non collegarsi. Suggerito: verificare con `ipconfig`
   (192.168.42.x = collegato, l'icona indica solo "niente internet"; 169.254.x =
   DHCP fallito), password mostrata sulla camera (spesso `1234567890`),
   "Non memorizzare" e ricollegarsi, togliere "connetti automaticamente" dalla
   rete di casa, provare 2,4 GHz, IP manuale 192.168.42.10/24 gateway
   192.168.42.1. In attesa dell'output di `ipconfig` e `netsh wlan show interfaces`.
2. Poi: provare `live_view.py` sulla camera reale e aprire `rtsp://192.168.42.1/live` in VLC.
3. Alternativa già documentata: modalità **Live** (QR, vedi `live/README.md`) verso
   un server RTMP locale (MediaMTX) → VLC su `rtsp://<IP-PC>:8554/yi`; qualità bassa (~1,4 Mbps).
4. Da esplorare: modalità **station** (camera sul Wi‑Fi di casa) sulla 4K. Nel repo
   esiste solo per la 4K+ (`4k+/wifi/Wi-Fi.DEBUG/start.sh`, hook in
   `/usr/local/share/network/restart.sh`); sulla 4K va verificato via telnet
   se esiste lo stesso meccanismo.
5. Non ancora fatto: applicare 120 Mbps alle altre modalità che l'utente usa
   (non ancora comunicate); provare la mod risoluzione ultra 4000x2700 /
   2000x1500 per 1.10.99 (generata, non testata).
6. Non verificato sulla 4K: `t app test record duals 0` (disattiva il salvataggio
   del `.SEC`), documentato solo per 4K+ 1.3.11 in `4k+/autoexec.ash_research/record.txt`.
7. Non realizzabili sulla 4K (limiti hardware): 4K60, H.265/HEVC.
8. Eventuale pull request del branch verso `master` quando l'utente lo chiede.

## 8. File pronti per la SD (creati durante la sessione)

`autoexec.ash` in uso, 120 Mbps (quello stabile):

```
#Yi 4k firmware 1.10.99 - test bitrate mod
#3840x2160 30P 16:9, high quality: 100 -> 120 mbps
writel 0xA06D48BC 0x42F00000 #120mbps

```

## 9. Regole di lavoro concordate

- Un cambiamento alla volta sulla camera; dopo ogni prova, registrazione lunga
  di verifica (5–10 min, scena complessa).
- Mai dump RAM da 16 MB su questo firmware; usare 2 MB a `0xA0600000` (o 64 KB a `0xA06D0000`).
- Se la camera si blocca: togliere la batteria, cancellare `autoexec.ash` dal PC.
- Nessun dato inventato: dire esplicitamente cosa è testato sulla camera reale e cosa no.
- Bitrate misurato a mano: `MB × 8 ÷ secondi` (in Windows 1 KB = 1024 byte).
