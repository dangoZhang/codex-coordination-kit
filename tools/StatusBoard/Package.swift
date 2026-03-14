// swift-tools-version: 6.0

import PackageDescription

let package = Package(
    name: "CoordinationStatusBoard",
    platforms: [
        .macOS(.v13)
    ],
    products: [
        .executable(name: "CoordinationStatusBoard", targets: ["CoordinationStatusBoard"])
    ],
    targets: [
        .executableTarget(
            name: "CoordinationStatusBoard",
            path: "Sources/CoordinationStatusBoard"
        )
    ]
)
