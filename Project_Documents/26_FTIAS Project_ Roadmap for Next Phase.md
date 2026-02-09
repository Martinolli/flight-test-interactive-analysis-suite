# FTIAS Project: Roadmap for Next Phase

**Project:** Flight Test Interactive Analysis Suite (FTIAS)  
**Current Status:** Sprint 2 (Phases 3 & 4) Complete  
**Next Phase:** Sprint 2 (Phase 5) - Comprehensive Testing & Parameter Management  
**Date:** February 9, 2026  
**Prepared By:** Manus AI

---

## 1. Overview of Next Phase

The next phase of Sprint 2 will focus on two key areas:
1.  **Comprehensive Automated Testing:** Achieving >90% code coverage and ensuring the long-term stability of the application.
2.  **Parameter Management:** Implementing the Excel upload functionality for the 985-parameter file.

This phase will solidify the backend, making it robust, reliable, and ready for future feature development.

---

## 2. Key Objectives for Next Phase

### 2.1. Comprehensive Automated Testing

-   **Objective:** Increase overall code coverage from 77% to >90%.
-   **Key Actions:**
    1.  **Integrate New Test Suites:** Add the newly created comprehensive test suites (`test_flight_tests_comprehensive.py`, `test_auth_comprehensive.py`, `test_parameters_comprehensive.py`) to the main test run.
    2.  **Target Low-Coverage Modules:** Write specific tests to cover the missing lines in `parameters.py`, `flight_tests.py`, and `auth.py`.
    3.  **Create Integration Tests:** Develop tests that simulate the full user workflow (e.g., login -> create flight test -> upload CSV -> retrieve data).
    4.  **Set Up CI/CD Pipeline:** Implement the recommended GitHub Actions workflow to automate testing on every push and pull request.

### 2.2. Parameter Management (Excel Upload)

-   **Objective:** Implement and test the Excel upload functionality for the 985-parameter file.
-   **Key Actions:**
    1.  **Implement `upload-excel` Endpoint:** Complete the code in `app/routers/parameters.py` to handle the Excel file upload.
    2.  **Handle Large Files:** Ensure the implementation can efficiently process the 985-parameter file.
    3.  **Implement Bulk Operations:** Use bulk create/update operations for efficient database interaction.
    4.  **Add Robust Error Handling:** Implement validation for required columns, data types, and duplicate entries.
    5.  **Write Comprehensive Tests:** Create specific tests for the Excel upload functionality, covering success cases, error cases, and edge cases.

---

## 3. Detailed Roadmap & Task Breakdown

### **Step 1: Repository & Branch Management**

1.  **Push All Current Changes:**
    ```bash
    git add .
    git commit -m "feat: complete Sprint 2 Phase 3-4 with CSV upload and fixes"
    git push origin main
    ```
2.  **Create Release Tag:**
    ```bash
    git tag -a v0.2.0 -m "Sprint 2 Phase 3-4 Complete"
    git push origin v0.2.0
    ```
3.  **Create New Feature Branch:**
    ```bash
    git checkout -b feature/sprint2-phase5
    ```

### **Step 2: Implement Parameter Excel Upload**

1.  **Complete `upload-excel` Endpoint:**
    -   Location: `app/routers/parameters.py`
    -   Use `openpyxl` to read the Excel file.
    -   Implement logic to iterate through rows and create/update parameters.
2.  **Implement Bulk Operations:**
    -   Use `db.bulk_save_objects()` or `db.bulk_update_mappings()` for efficiency.
3.  **Add Error Handling:**
    -   Validate required columns (`Name`, `Description`, `Unit`, etc.).
    -   Handle missing values and invalid data types.

### **Step 3: Comprehensive Testing**

1.  **Run All Test Suites:**
    ```bash
    pytest -v --cov=app
    ```
2.  **Identify Coverage Gaps:**
    -   Analyze the HTML coverage report (`htmlcov/index.html`).
    -   Focus on the red-highlighted lines in the low-coverage modules.
3.  **Write New Tests:**
    -   Add tests for the Excel upload functionality in `tests/test_parameters_comprehensive.py`.
    -   Add tests for error handling in `tests/test_flight_tests_comprehensive.py`.
    -   Add tests for token refresh and logout in `tests/test_auth_comprehensive.py`.
4.  **Create Integration Tests:**
    -   Create a new test file `tests/test_integration.py`.
    -   Write tests that combine multiple API calls to simulate real-world scenarios.

### **Step 4: CI/CD & DevOps**

1.  **Create GitHub Actions Workflow:**
    -   Create the file `.github/workflows/backend-tests.yml`.
    -   Add the recommended YAML configuration.
2.  **Configure Codecov:**
    -   Add the Codecov GitHub Action to the workflow.
    -   Add a Codecov badge to the `README.md`.
3.  **Set Up Branch Protection:**
    -   In the GitHub repository settings, add a branch protection rule for `main` and `develop`.
    -   Require status checks to pass before merging.
    -   Require pull request reviews.

### **Step 5: Documentation & Reporting**

1.  **Update `README.md`:**
    -   Add information about the new test suites and CI/CD pipeline.
    -   Add the Codecov badge.
2.  **Generate Final Sprint 2 QA Report:**
    -   Update the `QA_Report_Sprint2.md` with the final test results and coverage numbers.
3.  **Prepare for Sprint 3:**
    -   Create a new document `docs/Sprint3_Plan.md` outlining the goals for the next sprint (e.g., data visualization, real-time data).

---

## 4. Timeline & Milestones

-   **Day 1-2:** Implement and test the parameter Excel upload functionality.
-   **Day 3-4:** Write comprehensive tests to increase code coverage to >90%.
-   **Day 5:** Set up the CI/CD pipeline and branch protection rules.
-   **Day 6:** Generate the final QA report and prepare for the next sprint.

---

## 5. Conclusion

This roadmap provides a clear path to completing Sprint 2 and preparing the FTIAS project for future development. By focusing on comprehensive testing and completing the parameter management functionality, we will ensure a high-quality, robust, and reliable backend.

**Next Action:** Begin implementation of the parameter Excel upload.

---

**Prepared By:** Manus AI  
**Date:** February 9, 2026
