# iOS app: build, sign and ship to TestFlight

The app is native SwiftUI (iOS 17+, iPhone). The Xcode project is generated from `ios/project.yml` with
XcodeGen so the repository stays clean.

## 1. What you need

* A Mac with **Xcode 15.4 or newer** (Xcode 16 recommended).
* An **Apple Developer Program** membership (USD 99 / year, or INR equivalent) – required for TestFlight and the
  App Store. Enrol as an individual or as an organisation (an organisation needs a D-U-N-S number and shows
  your company name as seller).
* Your backend deployed on HTTPS (Apple's App Transport Security blocks plain HTTP).

## 2. Build and run

```bash
brew install xcodegen
```

```bash
cd ios && xcodegen generate && open BharatiDesk.xcodeproj
```

In Xcode: select the **BharatiDesk** target → *Signing & Capabilities* → tick *Automatically manage signing*
→ choose your Team. If `in.bharatiinvestigations.desk` is taken, change `PRODUCT_BUNDLE_IDENTIFIER` in
`project.yml` (and re-run `xcodegen`). Run on your iPhone (enable Developer Mode on the phone when asked).

On first launch enter your server URL (e.g. `https://api.your-domain.in`), then **First-time setup: create
account**. The first account becomes administrator.

Unit tests (model decoding against backend JSON shapes): ⌘U in Xcode.

## 3. TestFlight

1. App Store Connect → *My Apps* → **+** → New App → platform iOS, name "Bharati Investigation Desk",
   bundle id as above, SKU any text.
2. In Xcode: set the run destination to *Any iOS Device (arm64)* → **Product → Archive**.
3. Organizer → *Distribute App* → **TestFlight & App Store** → Upload.
4. In App Store Connect → TestFlight: answer the export-compliance question (the app uses only standard
   HTTPS/Keychain encryption; `ITSAppUsesNonExemptEncryption` is already `false`).
5. Add yourself as an **internal tester** – internal builds are available immediately without review.
   External testers need a short Beta App Review.

Increment `CURRENT_PROJECT_VERSION` in `project.yml` for every upload.

## 4. App Store (optional)

For your own business use, TestFlight (90-day builds, re-upload to renew) or an unlisted/custom app is enough.
For a public App Store listing you will need: privacy policy URL, App Privacy answers (the app collects
account email and user content – case files – used for app functionality only, not for tracking), screenshots
(6.7" and 6.5"), a demo account and a demo server for App Review, and an explanation that the AI analysis
runs on your server. The `PrivacyInfo.xcprivacy` manifest is included.

## 5. Signing notes

* Automatic signing creates the development and distribution certificates and profiles for you.
* No special entitlements beyond Data Protection (complete) are required. The custom URL scheme
  `bharatidesk://` (OAuth return) is declared in `Info.plist`.
* Keep the bundle id stable – changing it creates a new app record.
