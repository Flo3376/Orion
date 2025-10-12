const fs = require('fs');
const path = require('path');
const spawn = require('child_process').spawn;
const killPID = require('tree-kill');
const colors = require('colors');


// Variables globales pour le chemin du fichier exécutable, les PID et les buffers
let LISTEN = __dirname + '/../exe/listen/listen.exe';
let PIDS = {};
let BUFFERS = {};

// Fonction pour tuer un processus par ID
const kill = exports.kill = (id) => {
    let pid = PIDS[id];
    if (!pid) { return; }
    console.log('@@@ Killing [' + id + '] PID:', pid)
    try { killPID(pid); } catch (ex) { console.log('Kill Error:', ex) }
    PIDS[id] = undefined;
    BUFFERS[id] = undefined;
}

// Gestion des erreurs standard
const stdErr = exports.stdErr = (id, data, logback) => {
    const errorMessage = data.toString('utf8');
    const excludedStrings = [
        "AudioStateChanged",
        "recognizer_SpeechRecognitionRejected",
        "recognizer_SpeechDetected",
        "AudioLevel",
        "MaxAlternates",
        "BabbleTimeout",
        "InitialSilenceTimeout",
        "EndSilenceTimeout",
        "EndSilenceTimeoutAmbiguous",
        "ResponseSpeed",
        "ComplexResponseSpeed",
        "AdaptationOn",
        "PersistedBackgroundAdaptation",
        "Pause listening.",
        "Culture: fr-FR Kinect",
        "Culture: en-US Kinect",
    ];

    // Divise chaque message en lignes pour un traitement individuel
    const lines = errorMessage.split('\n');
    for (const line of lines) {
        let shouldExclude = false; // Flag pour déterminer si la ligne doit être exclue

        // Vérifie si la ligne contient une chaîne exclue
        for (const excludedString of excludedStrings) {
            if (line.includes(excludedString)) {
                shouldExclude = true;
                break; // Arrête de chercher dès qu'une exclusion est trouvée
            }
        }

        // Si la ligne ne doit pas être exclue, elle est passée à coloredLog
        if (!shouldExclude) {
            coloredLog(line);
        }
    }
}

// Configuration initiale pour colors (si nécessaire)
colors.setTheme({
    info: 'green',
    warn: 'yellow',
    error: 'red',
    hypothesized: 'yellow',
    recognized: 'green',
    standard: 'yellow'
});

// Affichage coloré des logs
function coloredLog(text) {
    const lines = text.split('\n');
    for (const line of lines) {
        if (line.trim() === "") {
            continue;
        }

        if (line.includes("recognizer_SpeechHypothesized")) {
            const match = /=>\s([\d,]+)/.exec(line);
            const infoMatch = /recognizer_SpeechHypothesized(.*?)=>/.exec(line);

            if (match && infoMatch) {
                const info = infoMatch[1];
                const words = info.trim().split(/\s+/);

                if (words.length > 3) {
                    const confidence = parseFloat(match[1].replace(',', '.'));
                    if (!isNaN(confidence) && confidence > 0.75) {
                        console.log(("    " + words.length + " mots consécutifs détectés").hypothesized);
                        console.log(('    ' + line.trimEnd()).hypothesized);
                    }
                }
            }
        } else if (line.includes("Init recognizer") || line.includes("Start listening...") || line.includes("Loading grammar cache")) {
            console.log(('    ' + line.trimEnd()).info);
        } else if (line.includes("SpeechRecognized")) {
            console.log(('            ' + line.trimEnd()).recognized);
        } else {
            console.log(('        ' + line.trimEnd()).standard);
        }
    }
}

// Fonction appelée à la fermeture du processus
const close = exports.close = (id, code, logback) => {
    logback('@@@ Process "listen.exe" closed with (' + code + ') for ID ' + id + ' pid: ' + PIDS[id])
}

// Fonction pour démarrer le processus de reconnaissance vocale
exports.start = (id, options, callback, logback) => {
    return new Promise((resolve, reject) => {
        kill(id);  // Assurez-vous de nettoyer toute instance précédente

        if (!options.grammar) {
            reject(new Error("No grammar specified"));
            return;
        }
        let grammar = path.normalize(options.grammar);
        let proc = path.normalize(options.proc || LISTEN);
        let confidence = options.confidence || '0.7';

        let args = ['-device', 'Microphone', '-grammar', grammar, '-confidence', confidence];
        if (options.language) { args.push('-language'); args.push(options.language); }
        if (options.recognizer) { args.push('-recognizer'); args.push(options.recognizer); }
        if (options.hotword) { args.push('-hotword'); args.push(options.hotword); }

        let child = spawn(proc, args);
        child.stdin.setEncoding('utf-8');
        child.stdout.on('data', (data) => { handleBuffer(id, data, callback,options); })
        child.stderr.on('data', (data) => { stdErr(id, data, console.log); })
        child.on('close', (code) => { close(id, code, console.log); })
        child.on('error', (err) => { close(id, err, console.log); });

        if (options.debug === true) {
            console.log('@@@ Starting Process', id, child.pid);
        }

        PIDS[id] = child.pid;
        BUFFERS[id] = '';

        resolve();  // Resolve the promise once setup is complete
    });
};
// Fonction pour gérer le buffer de données et extraire les résultats JSON
const handleBuffer = (id, data, callback,options) => {
    BUFFERS[id] += data.toString('utf8');
    let buffer = BUFFERS[id];

    let end = buffer.indexOf('</JSON>')
    if (end < 0) { return true; }

    let start = buffer.indexOf('<JSON>')
    if (start < 0) { return true; }

    let json = buffer.substring(start + 6, end);
    BUFFERS[id] = buffer.substring(end + 7);

    try { json = JSON.parse(json); } catch (ex) { console.log('Parsing Error:', ex, json); return; }

    //const audioBuffer = Buffer.from(json.base64, 'base64');
    //const timestamp = Date.now();
    //const filename = `./${options.path_input}/listen_${timestamp}.mp3`;

   // fs.writeFileSync(filename, audioBuffer);

    //console.log(`Base64 audio data saved to ${filename} with size: ${audioBuffer.length} bytes`);

    //delete json.base64;
    //json.base64Size = audioBuffer.length;

    callback(json);
}

exports.cleanUp = cleanUp;

// Fonction de nettoyage pour tuer tous les processus actifs
function cleanUp() {
    Object.keys(PIDS).forEach(id => {
        if (PIDS[id]) {
            console.log(`Cleaning up process ID ${id}`);
            kill(id); // Utilisation de la fonction kill définie précédemment
        }
    });
}

// Écoute du signal SIGINT pour gérer la fermeture propre
process.on('SIGINT', () => {
    console.log('Exiting...');
    cleanUp();
    process.exit(0); // Sortie propre du processus Node.js
});