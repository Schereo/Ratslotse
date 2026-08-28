// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "RatslotseAPI",
    platforms: [.iOS(.v17), .macOS(.v14)],
    products: [.library(name: "RatslotseAPI", targets: ["RatslotseAPI"])],
    targets: [
        .target(name: "RatslotseAPI"),
        .testTarget(
            name: "RatslotseAPITests",
            dependencies: ["RatslotseAPI"],
            resources: [.copy("Fixtures")]
        ),
    ]
)
