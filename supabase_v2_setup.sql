-- V2: 커스텀 정책 배틀을 위한 테이블 및 버킷 설정

-- 1. 개별 정책서 업로드 로그 (참가자)
create table if not exists public.policy_uploads (
  id uuid default gen_random_uuid() primary key,
  created_at timestamp with time zone default timezone('utc'::text, now()) not null,
  agency_name text not null,
  image_url text,
  parsed_data jsonb -- Gemini가 분석한 원본 JSON 데이터
);

-- 2. 배틀 결과 로그 (최종 엑셀)
create table if not exists public.battle_results (
  id uuid default gen_random_uuid() primary key,
  created_at timestamp with time zone default timezone('utc'::text, now()) not null,
  excel_url text,
  participants jsonb -- 참가한 대리점 이름 목록 (예: ["구로점", "강남점"])
);

-- 3. Storage 버킷 설정 (SQL로 버킷 생성이 안될 경우 대시보드에서 생성 필요)
-- 버킷 이름: policy-battles
-- Public Access: Enabled

-- 4. RLS 정책 (Storage) - 누구나 업로드 가능하게 설정 (테스트용)
-- Supabase 대시보드 -> Storage -> Policies 에서 'policy-battles' 버킷에 대해
-- INSERT, SELECT 권한을 anon(public) 롤에 부여해야 합니다.
