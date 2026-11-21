"""Gợi ý cặp ảnh gần trùng (pHash) để KIỂM TRA THỦ CÔNG, không tự xóa.

Cách chạy: python -m backend.tools.audit_near_duplicates --threshold 6
Cặp cùng một mẫu lá xuất hiện ở gallery và test có thể làm méo đánh giá.
"""

import argparse
import csv
from pathlib import Path

import cv2
import numpy as np

from ..config import SETTINGS
from ..db import connect


def perceptual_hash(image_path: Path) -> int:
    """pHash 64 bit dựa trên DCT 32×32; nhỏ hơn 8×8 DC để ít nhạy sáng."""
    img = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise ValueError(f"Không đọc được ảnh: {image_path}")
    sample = cv2.resize(img, (32, 32), interpolation=cv2.INTER_AREA).astype(np.float32)
    frequency = cv2.dct(sample)[:8, :8]
    values = frequency.flatten()
    median = np.median(values[1:])
    bits = values > median
    return sum(int(b) << i for i, b in enumerate(bits))


def audit_near_duplicates(db_path: Path, images_dir: Path,
                          threshold: int = 6, output: Path | None = None) -> list[dict]:
    """So sánh mọi cặp; ghi rõ cặp vượt qua split (rò rỉ tiềm năng)."""
    if not 0 <= threshold <= 64:
        raise ValueError("threshold cần ở khoảng 0..64")
    with connect(db_path) as con:
        rows = con.execute('SELECT file_name,group_id,split,relative_path FROM images '
                           'ORDER BY group_id,file_name').fetchall()
    if not rows:
        raise ValueError('CSDL chưa có ảnh để rà soát gần trùng')
    hashes = []
    for row in rows:
        data = dict(row)
        data['phash'] = perceptual_hash(images_dir / data['relative_path'])
        hashes.append(data)
    result = []
    for i, left in enumerate(hashes):
        for right in hashes[i + 1:]:
            hd = (left['phash'] ^ right['phash']).bit_count()
            if hd <= threshold:
                result.append({
                    'file_a': left['file_name'], 'group_a': left['group_id'], 'split_a': left['split'],
                    'file_b': right['file_name'], 'group_b': right['group_id'], 'split_b': right['split'],
                    'hamming_distance': hd, 'cross_split': left['split'] != right['split'],
                    'cross_group': left['group_id'] != right['group_id'],
                })
    result.sort(key=lambda x: (not x['cross_split'], x['hamming_distance']))
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open('w', newline='', encoding='utf-8-sig') as file:
            writer = csv.DictWriter(file, fieldnames=[
                'file_a', 'group_a', 'split_a', 'file_b', 'group_b', 'split_b',
                'hamming_distance', 'cross_split', 'cross_group',
            ])
            writer.writeheader(); writer.writerows(result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description='Kiểm tra rủi ro ảnh gần trùng')
    parser.add_argument('--db', type=Path, default=SETTINGS.database)
    parser.add_argument('--images', type=Path, default=SETTINGS.images_dir)
    parser.add_argument('--threshold', type=int, default=6)
    parser.add_argument('--output', type=Path, default=SETTINGS.database.parent / 'near_duplicate_review.csv')
    args = parser.parse_args()
    results = audit_near_duplicates(args.db, args.images, args.threshold, args.output)
    print(f"Đã ghi {len(results)} cặp nghi gần trùng vào {args.output}")
    print(f"Trong đó {sum(r['cross_split'] for r in results)} cặp khác tập (cần rà soát).")
    print('Chú ý: pHash chỉ là chỉ báo, KHÔNG tự động chứng minh hai ảnh trùng nhau.')


if __name__ == '__main__':
    main()
