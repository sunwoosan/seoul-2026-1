# demos/

2026-1학기 클라우드 프로그래밍 — Streamlit + GitHub Copilot 프로젝트 자료.

## 📂 폴더 구성

| 폴더 | 용도 | 누구를 위한 것 |
|---|---|---|
| [`typing_growth_tracker/`](typing_growth_tracker/) | **레퍼런스 데모** — 완성도 있는 예시 1개 | 모든 학생 (구현 수준의 기준점) |
| [`miniature-palm-tree/`](miniature-palm-tree/) | **학생 프로젝트 데모** — 점심시간 장소 추천 + 미세먼지 API 연동 | 주민경(M20261517) |
| [`_template/`](_template/) | **공통 보일러플레이트** — 빈 시작 골격 | 본인 프로젝트를 시작할 때 복사 |

---

## 🚀 어떻게 사용하나요

### 옵션 1. GitHub Template Repo로 시작 (권장)

본 저장소 자체가 학습용입니다. 본인 프로젝트는 **본인 GitHub 계정에 새 저장소**를 만들어 시작하세요.

```bash
# 1) 보일러플레이트만 빼서 본인 폴더로 복사
git clone https://github.com/sunwoosan/seoul-2026-1.git
cp -r seoul-2026-1/demos/_template ~/내프로젝트
cd ~/내프로젝트

# 2) 본인 GitHub 계정에 push
git init -b main
git add . && git commit -m "Initial commit"
gh repo create cloud-{학번}-{프로젝트명} --public --source=. --push
```

### 옵션 2. 로컬에서 바로 실행해 보기

```bash
cd typing_growth_tracker
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

샘플 데이터(`sample_data.csv`)를 사이드바에 업로드해보세요.

---

## 📋 본인 프로젝트 작성 흐름 (10~14주차)

| 주차 | 할 일 | 산출물 |
|---|---|---|
| 10 | 요구사항 작성 | `요구사항.docx` |
| 11 | 샘플 데이터 + v0 프로토타입 | `app.py` 기능 1 동작 |
| 12 | 기능 확장 + 디버깅 | 기능 2, 3 동작 |
| 13 | UI 정비 + 최종 배포 | Streamlit Cloud URL |
| 14 | 발표 + 상호 피드백 | 시연 + `PROMPT_LOG.md` 10개+ |

---

## 🛡️ 개인정보 / 보안 (필수 체크)

- [ ] 실제 학생 이름·번호가 든 CSV는 **절대 git에 commit 하지 않음** (`.gitignore`가 `*.csv` 차단)
- [ ] API 키·비밀번호는 `.streamlit/secrets.toml` 또는 Streamlit Cloud Secrets에만 저장
- [ ] Public 저장소여도 부끄럽지 않은 코드/데이터만 둘 것
- [ ] `PROMPT_LOG.md`는 매주 업데이트
