# Tubi TV Android App Test Cases
## Test Suite Summary
- **Platform**: Android
- **Package**: com.tubitv.dev
- **Screens Discovered**: 6
- **Main Flows Mapped**: 3
- **Screenshots Captured**: 26

## Test Cases

### TC-001: App Launch and Permissions
**Priority**: P0
**Type**: Functional
**Platform**: Android
**Preconditions**: 
- App is installed
- App has not been launched before
- Notifications permissions not granted

**Steps**:
1. Launch the app
   - Expected: Splash screen appears with Sign In and Skip options
   - Screenshot: step_001_splash.png
2. Wait for permissions dialog
   - Expected: Notification permissions dialog appears
   - Screenshot: step_021_splash.png
3. Tap "Allow"
   - Expected: Permissions granted, app continues to main flow
   - Screenshot: step_023_after_tap_Allow.png

### TC-002: Sign In Flow
**Priority**: P1
**Type**: Functional
**Platform**: Android
**Preconditions**:
- App is installed
- User has valid credentials
- At splash screen

**Steps**:
1. Tap "Sign In" on splash screen
   - Expected: Sign in screen appears with all auth options
   - Screenshot: step_002_before_tap_Sign_In.png
2. Verify sign in screen elements
   - Expected: Screen contains:
     * Email input field
     * Password input field with visibility toggle
     * Sign In button
     * Google sign in option
     * Facebook sign in option
     * "Forgot Password?" link
     * "Register" link
   - Screenshot: step_004_login.png

### TC-003: Password Reset Flow
**Priority**: P1
**Type**: Functional
**Platform**: Android
**Preconditions**:
- App is installed
- On sign in screen

**Steps**:
1. Tap "Reset it here" link
   - Expected: Password reset screen appears
   - Screenshot: step_006_after_tap_Reset_it_here.png
2. Verify password reset screen elements
   - Expected: Screen contains:
     * Email input field
     * Reset password button
     * Back button
     * Clear instructions
   - Screenshot: step_007_password_reset.png

### TC-004: Back Navigation
**Priority**: P2
**Type**: Navigation
**Platform**: Android
**Preconditions**:
- App is installed
- On password reset screen

**Steps**:
1. Press back button
   - Expected: Returns to sign in screen
   - Screenshot: step_008_after_back.png
2. Press back button again
   - Expected: Returns to splash screen
   - Screenshot: step_009_after_back.png

### TC-005: Skip Onboarding
**Priority**: P1
**Type**: Navigation
**Platform**: Android
**Preconditions**:
- App is installed
- On splash screen

**Steps**:
1. Tap "Skip" button
   - Expected: Bypasses sign in, enters main app interface
   - Screenshot: step_011_after_tap_element.png

### TC-006: Notification Permission Handling
**Priority**: P1
**Type**: Permissions
**Platform**: Android
**Preconditions**:
- App is installed
- Notifications not yet permitted

**Steps**:
1. Launch app and wait for permission dialog
   - Expected: Notification permission dialog appears
   - Screenshot: step_021_splash.png
2. Tap "Allow"
   - Expected: Permission granted, app continues
   - Screenshot: step_023_after_tap_Allow.png

### TC-007: Error State Handling
**Priority**: P2
**Type**: Error Handling
**Platform**: Android
**Preconditions**:
- App is installed
- Network connection available

**Steps**:
1. Monitor app transitions and error states
   - Expected: App handles state changes gracefully
   - Screenshot: step_025_after_tap_element.png
2. Verify error recovery
   - Expected: App returns to stable state after errors
   - Screenshot: step_026_home.png

## Coverage Matrix

| Screen Type | TC-001 | TC-002 | TC-003 | TC-004 | TC-005 | TC-006 | TC-007 |
|-------------|--------|--------|--------|--------|--------|--------|--------|
| Splash      | ✓      | ✓      |        | ✓      | ✓      | ✓      |        |
| Login       |        | ✓      | ✓      | ✓      |        |        |        |
| Password Reset |      |        | ✓      | ✓      |        |        |        |
| Home        |        |        |        |        | ✓      |        | ✓      |
| Permissions | ✓      |        |        |        |        | ✓      |        |
| Error States |       |        |        |        |        |        | ✓      |

## Known Issues
1. App stability issues observed during navigation
2. Some screens not accessible due to authentication requirements
3. Search functionality not fully tested due to access limitations

## Recommendations
1. Add more error handling test cases
2. Expand test coverage for main app features post-authentication
3. Add network condition test cases
4. Test orientation changes and system interrupts