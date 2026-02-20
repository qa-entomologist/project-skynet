# Books to Scrape QA Test Suite

## Test Suite Summary
This test suite covers the core functionality of the Books to Scrape e-commerce website (books.toscrape.com). The exploration discovered:
- 3 unique page types: Homepage, Category/Product Listing, and Product Detail
- Core user flows: browsing books, category navigation, and viewing product details
- Key UI components: category sidebar, product grid, detail views
- Screenshots directory: `/Users/dgapuz/DataDog Hackathon/screenshots/run_20260220_125855/`

## Test Cases

### TC-001: Browse Homepage and Navigate Categories
**Priority:** P1
**Type:** Smoke
**Preconditions:** None

| Step | Action | Expected Result | Screenshot |
|------|--------|----------------|------------|
| 1 | Navigate to https://books.toscrape.com | Homepage loads showing grid of books with categories in left sidebar | `step_001_homepage.png` |
| 2 | Click "Mystery" category in sidebar | Should navigate to Mystery category showing filtered list of mystery books | `step_002_before_click_Mystery.png`, `step_003_after_click_Mystery.png` |
| 3 | Verify category page elements | Page should show:
- "Mystery" category title
- Filtered book grid
- Breadcrumb navigation
- Category sidebar still visible | `step_004_category_listing.png` |

### TC-002: View Product Details
**Priority:** P1
**Type:** Functional
**Preconditions:** None

| Step | Action | Expected Result | Screenshot |
|------|--------|----------------|------------|
| 1 | Navigate to book detail page | Product detail page loads showing:
- Product title and image
- Price and availability
- Product information table
- Add to basket button | `step_010_product_detail.png` |
| 2 | Verify product information | Product information table should show:
- UPC
- Product Type
- Price (excl. tax)
- Price (incl. tax)
- Tax
- Availability
- Number of reviews | Same as above |

### TC-003: Category Navigation
**Priority:** P2
**Type:** Navigation
**Preconditions:** None

| Step | Action | Expected Result | Screenshot |
|------|--------|----------------|------------|
| 1 | Load homepage | Homepage loads with category sidebar | `step_001_homepage.png` |
| 2 | Verify all category links | Sidebar should show all book categories as clickable links | Same as above |
| 3 | Click each category | Each category should:
- Update URL with category name
- Filter book grid to category
- Show category name in breadcrumbs | `step_007_product_listing.png` |

## Edge Cases & Negative Tests

### TC-004: Empty Category Handling
**Priority:** P2
**Type:** Edge
**Preconditions:** None

| Step | Action | Expected Result |
|------|--------|----------------|
| 1 | Navigate to a category with no books | Should show "No books found" message |
| 2 | Verify UI elements | Category sidebar and navigation should still be present |

### TC-005: Invalid Product URLs
**Priority:** P2
**Type:** Negative
**Preconditions:** None

| Step | Action | Expected Result |
|------|--------|----------------|
| 1 | Navigate to non-existent product URL | Should show 404 page |
| 2 | Verify 404 page | Should have:
- Clear error message
- Navigation options to return home |

### TC-006: Product Grid Pagination
**Priority:** P2
**Type:** Functional
**Preconditions:** None

| Step | Action | Expected Result |
|------|--------|----------------|
| 1 | Navigate to category with >20 books | Pagination controls should appear |
| 2 | Click next page | Should load next set of books |
| 3 | Verify product count | Should maintain accurate count across pages |

## Coverage Matrix

| Page Type | Test Cases |
|-----------|------------|
| Homepage | TC-001, TC-003 |
| Category Listing | TC-001, TC-003, TC-004, TC-006 |
| Product Detail | TC-002, TC-005 |

## Screenshot Inventory
- `step_001_homepage.png`: Homepage with book grid and category sidebar
- `step_002_before_click_Mystery.png`: Homepage before category click
- `step_003_after_click_Mystery.png`: Mystery category page
- `step_004_category_listing.png`: Category listing page layout
- `step_007_product_listing.png`: Product grid with pagination
- `step_010_product_detail.png`: Product detail page layout