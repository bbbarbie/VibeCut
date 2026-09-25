// On-device Vision pass over shot thumbnails. Nothing leaves the machine.
//
//   vibevision img1.jpg img2.jpg ...   -> one JSON object per line on stdout
//
// Gives the index what numpy can't: what is in the frame (labels, faces),
// an embedding to cluster by subject, and Apple's aesthetics score as the
// per-shot quality number the tech plan calls for.

import Foundation
import Vision

struct Out: Encodable {
    let path: String
    let labels: [[String: Double]]   // [{label: confidence}], top few
    let faces: Int
    let faceArea: Double             // largest face as fraction of frame -- shot-size proxy
    let aesthetic: Double?           // -1...1
    let utility: Bool?               // screenshots, documents, receipts
    let embedding: [Float]
    let error: String?
}

func analyse(_ path: String) async -> Out {
    let url = URL(fileURLWithPath: path)
    do {
        let labels = try await ClassifyImageRequest().perform(on: url)
            .filter { $0.confidence > 0.15 }
            .sorted { $0.confidence > $1.confidence }
            .prefix(8)
            .map { [$0.identifier: Double($0.confidence)] }
        let faces = try await DetectFaceRectanglesRequest().perform(on: url)
        let area = faces.map { Double($0.boundingBox.width * $0.boundingBox.height) }.max() ?? 0
        var aesthetic: Double? = nil
        var utility: Bool? = nil
        if let a = try? await CalculateImageAestheticsScoresRequest().perform(on: url) {
            aesthetic = Double(a.overallScore)
            utility = a.isUtility
        }
        let fp = try await GenerateImageFeaturePrintRequest().perform(on: url)
        var emb = [Float]()
        fp.data.withUnsafeBytes { raw in
            if fp.elementType == .float {
                emb = Array(raw.bindMemory(to: Float.self))
            } else {
                emb = raw.bindMemory(to: Double.self).map { Float($0) }
            }
        }
        return Out(path: path, labels: Array(labels), faces: faces.count, faceArea: area,
                   aesthetic: aesthetic, utility: utility, embedding: emb, error: nil)
    } catch {
        return Out(path: path, labels: [], faces: 0, faceArea: 0, aesthetic: nil,
                   utility: nil, embedding: [], error: "\(error)")
    }
}

// `vibevision --faces a.jpg b.jpg ...`: face boxes only, for every sampled
// second of a clip (trim needs to know when a person is in or leaving frame).
struct FaceOut: Encodable {
    let path: String
    let faces: [[Double]]   // [x, y, w, h], normalised, origin bottom-left
}

func faces(_ path: String) async -> FaceOut {
    let url = URL(fileURLWithPath: path)
    let found = (try? await DetectFaceRectanglesRequest().perform(on: url)) ?? []
    return FaceOut(path: path, faces: found.map {
        [Double($0.boundingBox.origin.x), Double($0.boundingBox.origin.y),
         Double($0.boundingBox.width), Double($0.boundingBox.height)]
    })
}

var args = Array(CommandLine.arguments.dropFirst())
let enc = JSONEncoder()
if args.first == "--faces" {
    args.removeFirst()
    let found = await withTaskGroup(of: (Int, FaceOut).self) { group in
        for (i, p) in args.enumerated() { group.addTask { (i, await faces(p)) } }
        var acc = [(Int, FaceOut)]()
        for await r in group { acc.append(r) }
        return acc.sorted { $0.0 < $1.0 }.map { $0.1 }
    }
    for r in found {
        if let d = try? enc.encode(r), let s = String(data: d, encoding: .utf8) { print(s) }
    }
    exit(0)
}
let paths = args
let results = await withTaskGroup(of: (Int, Out).self) { group in
    for (i, p) in paths.enumerated() {
        group.addTask { (i, await analyse(p)) }
    }
    var acc = [(Int, Out)]()
    for await r in group { acc.append(r) }
    return acc.sorted { $0.0 < $1.0 }.map { $0.1 }
}
for r in results {
    if let d = try? enc.encode(r), let s = String(data: d, encoding: .utf8) { print(s) }
}
