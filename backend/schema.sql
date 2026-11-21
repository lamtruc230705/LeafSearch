-- Tệp schema chuẩn. Mỗi ảnh lưu 4 vector, metadata và phân tập.
-- BLOB chứa float32 theo little-endian, đúng thứ tự chiều của pipeline.
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS categories (
    group_id TEXT PRIMARY KEY,
    description TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS images (
    image_id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_name TEXT NOT NULL UNIQUE,
    group_id TEXT NOT NULL REFERENCES categories(group_id),
    relative_path TEXT NOT NULL UNIQUE,
    sha256 TEXT NOT NULL UNIQUE,
    pixel_sha256 TEXT NOT NULL UNIQUE,
    width INTEGER NOT NULL CHECK(width > 0),
    height INTEGER NOT NULL CHECK(height > 0),
    split TEXT NOT NULL CHECK(split IN ('gallery','validation','test')),
    mask_ratio REAL NOT NULL CHECK(mask_ratio BETWEEN 0 AND 1),
    quality_status TEXT NOT NULL CHECK(quality_status IN ('ok','review')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_images_group_split ON images(group_id, split);

CREATE TABLE IF NOT EXISTS features (
    image_id INTEGER NOT NULL REFERENCES images(image_id) ON DELETE CASCADE,
    feature_group TEXT NOT NULL CHECK(feature_group IN ('color','shape','ridge','texture')),
    version TEXT NOT NULL,
    dimension INTEGER NOT NULL CHECK(dimension > 0),
    vector BLOB NOT NULL,
    PRIMARY KEY(image_id, feature_group, version)
);
CREATE INDEX IF NOT EXISTS ix_features_version ON features(version, feature_group);

CREATE TABLE IF NOT EXISTS feature_stats (
    feature_group TEXT NOT NULL,
    version TEXT NOT NULL,
    dimension INTEGER NOT NULL,
    gallery_count INTEGER NOT NULL,
    mean_vector BLOB NOT NULL,
    scale_vector BLOB NOT NULL,
    PRIMARY KEY(feature_group, version)
);

CREATE TABLE IF NOT EXISTS search_logs (
    search_id INTEGER PRIMARY KEY AUTOINCREMENT,
    query_file_name TEXT NOT NULL,
    version TEXT NOT NULL,
    weights_json TEXT NOT NULL,
    results_json TEXT NOT NULL,
    runtime_ms REAL NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS evaluation_runs (
    evaluation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    split TEXT NOT NULL CHECK(split IN ('validation','test')),
    version TEXT NOT NULL,
    weights_json TEXT NOT NULL,
    metrics_json TEXT NOT NULL,
    details_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
