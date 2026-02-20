# Books to Scrape - QA Test Suite

## Test Suite Summary
This test suite covers the core functionality of the Books to Scrape website, including:
- Homepage navigation and book browsing
- Category filtering and navigation
- Product detail page functionality
- Add to basket functionality
- Basic site navigation and breadcrumbs

Pages discovered: 3
Main flows mapped: 2
Test cases created: 8

## Test Cases

### TC-001: Browse and View Homepage
**Priority:** P0
**Type:** Smoke
**Preconditions:** None

| Step | Action | Expected Result |
|------|--------|----------------|
| 1 | Navigate to https://books.toscrape.com | Homepage loads with book catalog grid |
| 2 | Scan homepage content | Should see: header with logo, category sidebar, book grid with images/prices/titles, pagination |
| 3 | Verify book grid items | Each book should show: cover image, title, price in £, stock status, "Add to basket" button |
| 4 | Check category sidebar | Should display complete list of book categories |
| 5 | Verify pagination | Should show total products count and page navigation if more than 20 books |

### TC-002: Navigate Book Categories
**Priority:** P1
**Type:** Navigation
**Preconditions:** User is on homepage

| Step | Action | Expected Result |
|------|--------|----------------|
| 1 | Click "Mystery" category in sidebar | Should navigate to Mystery category page |
| 2 | Verify category page | Should show: breadcrumb trail, "Mystery" title, filtered book list |
| 3 | Check book listings | Only Mystery genre books should be displayed |
| 4 | Verify navigation elements | Sidebar categories and breadcrumbs should remain accessible |
| 5 | Navigate back via breadcrumb | Should return to homepage |

### TC-003: View Product Details
**Priority:** P0
**Type:** Functional
**Preconditions:** User is on homepage

| Step | Action | Expected Result |
|------|--------|----------------|
| 1 | Click a book title | Should navigate to product detail page |
| 2 | Verify product information | Should show: large cover image, title, price, description |
| 3 | Check product details table | Should display: UPC, product type, prices (with/without tax), availability, reviews |
| 4 | Verify "Add to basket" button | Button should be visible and clickable |
| 5 | Check breadcrumb navigation | Should show correct category path to current book |

### TC-004: Add Book to Basket
**Priority:** P0
**Type:** Functional
**Preconditions:** User is on a product detail page

| Step | Action | Expected Result |
|------|--------|----------------|
| 1 | Click "Add to basket" button | Should add item to basket |
| 2 | Verify success message | Should show confirmation message |
| 3 | Check basket status | Basket count/total should update |
| 4 | Verify product still available | Stock status should update if quantity limited |

### TC-005: Category Navigation Breadcrumbs
**Priority:** P2
**Type:** Navigation
**Preconditions:** None

| Step | Action | Expected Result |
|------|--------|----------------|
| 1 | Navigate to a category | Should show proper breadcrumb trail |
| 2 | Click breadcrumb links | Should navigate to correct level |
| 3 | Click home in breadcrumbs | Should return to homepage |

### TC-006: Direct URL Access (Edge Case)
**Priority:** P2
**Type:** Edge
**Preconditions:** None

| Step | Action | Expected Result |
|------|--------|----------------|
| 1 | Access product URL directly | Should load product page correctly |
| 2 | Access category URL directly | Should load category page correctly |
| 3 | Access invalid product URL | Should show appropriate error page |

### TC-007: Stock Status Edge Cases
**Priority:** P2
**Type:** Edge
**Preconditions:** None

| Step | Action | Expected Result |
|------|--------|----------------|
| 1 | View in-stock product | Should show "In stock" and allow adding to basket |
| 2 | View low-stock product | Should show remaining quantity |
| 3 | View out-of-stock product | Should show "Out of stock" and disable basket button |

### TC-008: Navigation Error Cases
**Priority:** P3
**Type:** Negative
**Preconditions:** None

| Step | Action | Expected Result |
|------|--------|----------------|
| 1 | Access non-existent category | Should show appropriate error page |
| 2 | Access malformed URLs | Should show 404 page |
| 3 | Use browser back/forward | Should maintain proper page state |

## Coverage Matrix

| Page Type | Test Cases |
|-----------|------------|
| Homepage | TC-001, TC-002 |
| Category Listing | TC-002, TC-005, TC-006, TC-008 |
| Product Detail | TC-003, TC-004, TC-006, TC-007 |
| Error Pages | TC-006, TC-008 |

## Critical Paths to Test
1. Homepage → Category → Product → Add to Basket
2. Direct Product URL → Add to Basket
3. Category Navigation via Breadcrumbs
4. Error Page Recovery

## Accessibility Considerations
- All images should have alt text
- Price information should be properly marked up
- Navigation should be keyboard-accessible
- Color contrast should meet WCAG standards
- Form controls should have proper labels
- Breadcrumbs should provide context