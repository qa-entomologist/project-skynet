# Tubi TV Test Suite

## Summary
This test suite covers the core functionality of Tubi TV, a free streaming service. Key areas tested include video playback, navigation, search, kids mode, responsive design, and page health.

## Test Cases

### TC-001: Video Content Playback
**Priority:** P0
**Type:** Core Function

| Step | Action | Expected Result |
|------|--------|----------------|
| 1 | Navigate to homepage | Homepage loads with featured content and navigation |
| 2 | Click on any movie/show thumbnail | Detail page opens showing title, synopsis, cast, and play button |
| 3 | Click "Play FREE" button | Video player launches |
| 4 | Verify player controls | Play/pause, volume, fullscreen, and subtitle controls present |

### TC-002: Main Navigation
**Priority:** P1
**Type:** Navigation

| Step | Action | Expected Result |
|------|--------|----------------|
| 1 | Click "Movies" in header | Movies page loads with categories and featured films |
| 2 | Click "TV Shows" in header | TV Shows page loads with series categories |
| 3 | Click "Live TV" in header | Live TV page loads with streaming channels |
| 4 | Click "Browse" dropdown | Genre categories appear in dropdown |

### TC-003: Kids Mode
**Priority:** P1
**Type:** Mode Change

| Step | Action | Expected Result |
|------|--------|----------------|
| 1 | Click "Tubi Kids" in header | Switches to kids mode |
| 2 | Verify header changes | Header simplifies to Browse, Exit Kids, Register, Sign In |
| 3 | Verify content filtering | Only kid-friendly content shown |
| 4 | Click "Exit Kids" | Returns to normal mode with full content |

### TC-004: Search Functionality
**Priority:** P1
**Type:** Function

| Step | Action | Expected Result |
|------|--------|----------------|
| 1 | Type valid query in search bar | Results appear with relevant titles |
| 2 | Search for "scooby doo" | Shows Scooby-Doo related content |
| 3 | Submit empty search | Shows error message or placeholder |
| 4 | Search with special characters | Handles special characters appropriately |

### TC-005: Responsive Design
**Priority:** P2
**Type:** Responsive

| Step | Action | Expected Result |
|------|--------|----------------|
| 1 | View on mobile (375x812) | Layout adapts with hamburger menu |
| 2 | Check content grid | Switches to 2-column layout |
| 3 | Verify touch targets | Buttons and links appropriately sized |
| 4 | Test menu navigation | Mobile menu functions correctly |

### TC-006: Page Health
**Priority:** P2
**Type:** Technical

| Step | Action | Expected Result |
|------|--------|----------------|
| 1 | Check images | No broken images |
| 2 | Verify alt text | All images have descriptive alt text |
| 3 | Test form inputs | All inputs properly labeled |
| 4 | Check console | No JavaScript errors |

### TC-007: Content Categories
**Priority:** P1
**Type:** Navigation

| Step | Action | Expected Result |
|------|--------|----------------|
| 1 | Open Browse dropdown | Category list appears |
| 2 | Click genre category | Shows filtered content for selected genre |
| 3 | Verify content cards | Each card shows title, year, and FREE badge |
| 4 | Test carousel navigation | Horizontal scrolling works in content rows |

## Coverage Matrix

| Feature Area | Test Cases | Priority |
|-------------|------------|----------|
| Video Playback | TC-001 | P0 |
| Navigation | TC-002, TC-007 | P1 |
| Kids Mode | TC-003 | P1 |
| Search | TC-004 | P1 |
| Responsive | TC-005 | P2 |
| Technical | TC-006 | P2 |