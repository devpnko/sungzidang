-- 테이블이 없어서 발생한 오류입니다. 아래 쿼리를 실행해주세요.

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

-- 3. 권한 설정 (RLS가 켜져있다면 필요, 테스트용으로 모든 권한 부여)
alter table public.policy_uploads enable row level security;
create policy "Enable all access for all users" on public.policy_uploads for all using (true) with check (true);

alter table public.battle_results enable row level security;
create policy "Enable all access for all users" on public.battle_results for all using (true) with check (true);
