---
type: "query"
date: "2026-08-01T13:10:23.604573+00:00"
question: "Locate concrete application evidence for Lamha media ingest, decoder, metadata, preview, companion, video, raw, asset, and schema planning."
contributor: "graphify"
outcome: "useful"
source_nodes: ["MediaService", "StorageCore", "AssetJobRepository", "AssetFile", "ImageDimensions", "RawExtractedFormat"]
---

# Q: Locate concrete application evidence for Lamha media ingest, decoder, metadata, preview, companion, video, raw, asset, and schema planning.

## Answer

Useful evidence exists in MediaService, StorageCore, AssetJobRepository, media utilities, asset/database records, and enums. The traversal specifically exposes thumbnail generation, video conversion, original-image extraction, sidecar jobs, asset file records, image/video dimensions, codecs, colorspace, and storage moves. These are implementation evidence only; they do not justify copying Immich architecture or asserting unverified Lamha behavior.

## Outcome

- Signal: useful

## Source Nodes

- MediaService
- StorageCore
- AssetJobRepository
- AssetFile
- ImageDimensions
- RawExtractedFormat