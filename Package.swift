// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "HippoDEMO",
    platforms: [.macOS(.v14)],
    products: [
        .executable(name: "HippoJarvis", targets: ["HippoJarvis"])
    ],
    targets: [
        .executableTarget(
            name: "HippoJarvis",
            path: "Sources/HippoJarvis"
        )
    ]
)
