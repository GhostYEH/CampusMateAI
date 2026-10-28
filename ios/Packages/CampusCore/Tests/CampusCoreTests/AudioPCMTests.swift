import Foundation
import Testing
@testable import CampusCore

@Suite("Audio frame boundaries")
struct AudioPCMTests {
    @Test func oddNetworkChunksKeepTheRemainingSampleByte() throws {
        var framer = PCM16Framer()
        #expect(try framer.append(Data([0, 128, 255])) == [-1])
        #expect(try framer.append(Data([127, 0, 0])) == [Float(Int16.max) / 32768, 0])
        #expect(!framer.hasPartialSample)
    }
    @Test func compressedOrOversizedFramesAreRejected() {
        var framer = PCM16Framer()
        #expect(throws: (any Error).self) { try framer.append(Data("OggS".utf8)) }
        #expect(throws: (any Error).self) { try framer.append(Data(repeating: 0, count: 1_048_577)) }
    }
    @Test func resetDiscardsPartialOldTurnAudio() throws {
        var framer = PCM16Framer()
        _ = try framer.append(Data([255])); framer.reset()
        #expect(try framer.append(Data([0, 0])) == [0])
    }
}
