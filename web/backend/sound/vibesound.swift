// On-device sound classification of a clip's audio. Nothing leaves the machine.
//
//   vibesound a.wav b.wav ...   -> one JSON object per line on stdout
//
// Apple's built-in sound classifier (SoundAnalysis, classifier version1)
// tells a voice from music, which the level-based voiced mask can't: loud
// music reads as talking, and talking clips are never trimmed. Per window
// of about a second: how sure it is there's speech, music, singing, laughter.

import AVFoundation
import Foundation
import SoundAnalysis

let voiceIds: Set<String> = ["speech", "conversation", "whispering", "shout", "yell", "narration_monologue",
                             "child_speech_kid_speaking", "male_speech_man_speaking", "female_speech_woman_speaking"]
let musicIds: Set<String> = ["music"]
let singIds: Set<String> = ["singing", "choir", "rapping", "humming", "chant"]
let laughIds: Set<String> = ["laughter", "giggling", "belly_laugh", "chuckle_chortle", "baby_laughter"]

struct Window: Encodable {
    let t: Double
    let d: Double
    let voice: Double
    let music: Double
    let singing: Double
    let laughter: Double
}

struct Out: Encodable {
    let path: String
    let windows: [Window]
    let error: String?
}

final class Collector: NSObject, SNResultsObserving {
    var windows: [Window] = []
    var failure: String?

    func request(_ request: SNRequest, didProduce result: SNResult) {
        guard let r = result as? SNClassificationResult else { return }
        func top(_ ids: Set<String>) -> Double {
            r.classifications.filter { ids.contains($0.identifier) }.map { $0.confidence }.max() ?? 0
        }
        windows.append(Window(t: r.timeRange.start.seconds, d: r.timeRange.duration.seconds,
                              voice: top(voiceIds), music: top(musicIds),
                              singing: top(singIds), laughter: top(laughIds)))
    }

    func request(_ request: SNRequest, didFailWithError error: Error) {
        failure = error.localizedDescription
    }
}

func analyse(_ path: String) -> Out {
    do {
        let req = try SNClassifySoundRequest(classifierIdentifier: .version1)
        req.windowDuration = CMTime(seconds: 1.0, preferredTimescale: 1000)
        req.overlapFactor = 0.5
        let analyzer = try SNAudioFileAnalyzer(url: URL(fileURLWithPath: path))
        let c = Collector()
        try analyzer.add(req, withObserver: c)
        analyzer.analyze()
        return Out(path: path, windows: c.windows, error: c.failure)
    } catch {
        return Out(path: path, windows: [], error: error.localizedDescription)
    }
}

let enc = JSONEncoder()
for path in CommandLine.arguments.dropFirst() {
    if let data = try? enc.encode(analyse(path)), let line = String(data: data, encoding: .utf8) {
        print(line)
        fflush(stdout)
    }
}
