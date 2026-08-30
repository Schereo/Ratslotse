// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "RatslotseFeatures",
    platforms: [.iOS(.v17)],
    products: [.library(name: "RatslotseFeatures", targets: ["RatslotseFeatures"])],
    dependencies: [
        .package(path: "../RatslotseAPI"),
        .package(path: "../RatslotseDesign"),
    ],
    targets: [
        .target(
            name: "RatslotseFeatures",
            dependencies: ["RatslotseAPI", "RatslotseDesign"]
        )
    ]
)
