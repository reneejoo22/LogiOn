# LogiOn 
앱 프론트

## 화면 구성
- `HomeScreen.kt`
    - 오늘 배송 현황 확인
    - 다음 배송지 정보 표시
    - 배송지 위치 확인
    - 음성 입력 상태 표시
- `RouteScreen.kt`
    - 전체 / 진행 중 / 완료 배송 목록
    - 빠른 배송 완료 및 완료 취소
    - 배송지 상세 화면 연결
- `ScanScreen.kt`
    - 바코드 스캔
    - 수기 입력
    - 상품 이상 보고
- `MoreScreen.kt`
    - 기사 정보 확인
    - 도움말, 공지사항 등 추가 메뉴
- `StopDetailSheet.kt`
    - 배송지 상세 정보
    - 상품 체크
    - 배송 완료 및 완료 취소

## 주요 공통 파일
- `LogiOnApp.kt`
    - 화면 전환 및 앱 전체 상태 관리
- `BottomNavigation.kt`
    - 하단 네비게이션
- `VoiceDock.kt`
    - 음성 입력 UI
- `AppTopBar.kt`
    - 공통 상단바
- `MockDat.kt`
    - 배송 Mock 데이터
- `MockUser.kt`
    - 기사 Mock 데이터

## 개발 환경
- Android Studio
- Kotlin
- Jetpack Compose
- Material3

## 실행 방법
1. `android` 폴더를 Android Studio에서 엽니다.
2. Gradle Sync가 완료될 때까지 기다립니다.
3. Android 에뮬레이터 또는 실제 기기를 선택합니다.
4. `app` 모듈을 실행합니다.

## 현재 상태
현재는 UI/UX 프로토타입 단계이며 Mock 데이터를 사용합니다.
추후 백엔드 및 음성 LLM 기능과 연동할 예정입니다.