// Place names for a clip's GPS, for captions ("Shibuya", "Golden Gate Park").
//
//   vibeplace 35.659,139.700 37.769,-122.486 ...   -> one JSON object per line
//
// Apple's geocoder on this Mac. It sends only the coordinates to Apple's
// free location service (no frames, no audio, no key, no cost) and returns
// the neighbourhood, city and any named place there. Apple throttles it, so
// callers round coordinates and cache answers; one request at a time here.

import CoreLocation
import Foundation

struct Out: Encodable {
    let at: String
    let name: String?
    let place: String?      // a named place: a park, a landmark, a venue
    let area: String?       // neighbourhood
    let city: String?
    let country: String?
    let error: String?
}

func lookup(_ at: String) async -> Out {
    let p = at.split(separator: ",").compactMap { Double($0.trimmingCharacters(in: .whitespaces)) }
    guard p.count == 2 else { return Out(at: at, name: nil, place: nil, area: nil, city: nil, country: nil, error: "bad coordinate") }
    do {
        let marks = try await CLGeocoder().reverseGeocodeLocation(CLLocation(latitude: p[0], longitude: p[1]))
        guard let m = marks.first else { return Out(at: at, name: nil, place: nil, area: nil, city: nil, country: nil, error: "nothing there") }
        return Out(at: at, name: m.name, place: m.areasOfInterest?.first, area: m.subLocality,
                   city: m.locality, country: m.country, error: nil)
    } catch {
        return Out(at: at, name: nil, place: nil, area: nil, city: nil, country: nil, error: error.localizedDescription)
    }
}

let enc = JSONEncoder()
for at in CommandLine.arguments.dropFirst() {
    let out = await lookup(at)
    if let d = try? enc.encode(out), let line = String(data: d, encoding: .utf8) {
        print(line)
        fflush(stdout)
    }
    try? await Task.sleep(nanoseconds: 300_000_000)   // stay under Apple's rate limit
}
