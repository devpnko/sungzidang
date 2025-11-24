-- 2-Bucket Strategy Setup
-- 기존 테이블들은 그대로 유지하되, 버킷만 새로 설정합니다.

-- 1. Storage 버킷 생성 (SQL로 생성이 안될 경우 대시보드에서 생성 필요)
-- Bucket Name: uploads
-- Public Access: Enabled
-- 용도: 모든 원본 이미지 (simple-ocr/, policy-battle/ 폴더로 구분)

-- Bucket Name: exports
-- Public Access: Enabled
-- 용도: 생성된 결과물 (simple-excel/, battle-results/ 폴더로 구분)

-- 2. Storage 권한 설정 (Policies)
-- 'uploads' 버킷에 대해: INSERT, SELECT 권한 부여 (Target role: anon)
-- 'exports' 버킷에 대해: INSERT, SELECT 권한 부여 (Target role: anon)
