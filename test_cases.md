# Tubi TV Test Suite

## Overview
This test suite covers the core functionality of Tubi TV (tubitv.com), a free streaming service offering movies, TV shows, and live TV content. The test cases focus on critical user flows, content discovery, playback, search, authentication, and special modes like Kids mode.

## Test Environment
- Desktop browser (1920x1080)
- Mobile viewport (375x812)
- No authentication required for basic browsing
- Test content: Movies, TV shows, kids content

## Test Cases

### TC-001: Homepage Content Display and Navigation
**Priority:** P0
**Type:** Smoke

| Step | Action | Expected Result | Screenshot |
|------|--------|-----------------|------------|
| 1 | Navigate to tubitv.com | Homepage loads with header navigation, featured content, and content rows | homepage.png |
| 2 | Verify header items | Shows: Browse, Movies, TV Shows, Live TV, Español, Kids mode, Sign In | - |
| 3 | Scroll through content rows | Content rows load smoothly, thumbnails visible | - |
| 4 | Hover over content items | Play button appears, title info shown | - |

### TC-002: Movie Detail Page and Playback
**Priority:** P0
**Type:** Functional

| Step | Action | Expected Result | Screenshot |
|------|--------|-----------------|------------|
| 1 | Click any movie thumbnail | Movie detail page opens | movie_detail.png |
| 2 | Verify movie information | Shows title, year, rating, duration, description | - |
| 3 | Click Play button | Video player launches | player.png |
| 4 | Verify player controls | Play/pause, timeline, volume controls functional | - |

### TC-003: Search Functionality
**Priority:** P1
**Type:** Functional

| Step | Action | Expected Result | Screenshot |
|------|--------|-----------------|------------|
| 1 | Enter valid movie title "Shrek" | Search results show relevant matches | search_results.png |
| 2 | Click search result | Navigates to correct content detail page | - |
| 3 | Search "xyzabc123notamovie" | Shows "No results found" message | no_results.png |
| 4 | Verify search suggestions | Shows trending/popular content alternatives | - |

### TC-004: Kids Mode Toggle
**Priority:** P1
**Type:** Mode

| Step | Action | Expected Result | Screenshot |
|------|--------|-----------------|------------|
| 1 | Click "Tubi Kids" button | Switches to kids interface | kids_mode.png |
| 2 | Verify content filtering | Only family-friendly content shown | - |
| 3 | Verify UI changes | Different color scheme, simplified navigation | - |
| 4 | Click "Exit Kids" | Returns to regular mode | - |

### TC-005: Authentication Flows
**Priority:** P1
**Type:** Functional

| Step | Action | Expected Result | Screenshot |
|------|--------|-----------------|------------|
| 1 | Click Sign In | Login form appears | login.png |
| 2 | Verify login options | Email/password, social logins available | - |
| 3 | Click Register | Registration form appears | register.png |
| 4 | Verify form fields | All required fields present with validation | - |

### TC-006: Mobile Responsive Design
**Priority:** P2
**Type:** Responsive

| Step | Action | Expected Result | Screenshot |
|------|--------|-----------------|------------|
| 1 | View on mobile (375x812) | Layout adjusts for mobile | mobile.png |
| 2 | Verify navigation | Menu collapses to hamburger | - |
| 3 | Verify content grid | Single column layout | - |
| 4 | Test touch interactions | Buttons/controls properly sized | - |

### TC-007: Legal/Support Pages
**Priority:** P2
**Type:** Navigation

| Step | Action | Expected Result | Screenshot |
|------|--------|-----------------|------------|
| 1 | Access Terms of Use | Terms page loads with sections | terms.png |
| 2 | Access Privacy Policy | Privacy policy loads | privacy.png |
| 3 | Access Support | Help center/contact form loads | support.png |
| 4 | Verify navigation | All legal/support links functional | - |

### TC-008: Content Categories
**Priority:** P1
**Type:** Navigation

| Step | Action | Expected Result | Screenshot |
|------|--------|-----------------|------------|
| 1 | Click Movies | Shows movie categories/filters | movies.png |
| 2 | Click TV Shows | Shows TV categories/filters | tv.png |
| 3 | Click Live TV | Shows available live channels | live.png |
| 4 | Test category filters | Content updates per selection | - |

### TC-009: Page Health Check
**Priority:** P2
**Type:** Accessibility

| Step | Action | Expected Result | Screenshot |
|------|--------|-----------------|------------|
| 1 | Check homepage health | No broken images/links | - |
| 2 | Verify alt text | Images have descriptive alt text | - |
| 3 | Check form labels | All inputs properly labeled | - |
| 4 | Monitor console | No JavaScript errors | - |

## Coverage Matrix

| Feature Area | Test Cases | Priority |
|-------------|------------|----------|
| Core Navigation | TC-001, TC-008 | P0 |
| Content Playback | TC-002 | P0 |
| Search | TC-003 | P1 |
| Kids Mode | TC-004 | P1 |
| Authentication | TC-005 | P1 |
| Responsive Design | TC-006 | P2 |
| Support/Legal | TC-007 | P2 |
| Accessibility | TC-009 | P2 |