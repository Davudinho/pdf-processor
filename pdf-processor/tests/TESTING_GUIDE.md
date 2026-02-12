# Testing Guide - Step by Step

This guide will help you test the PDF Intelligence System systematically.

---

## 📋 Overview

The test suite includes 4 test files:

| File | Purpose | Uses OpenAI | Time | Recommended |
|------|---------|-------------|------|-------------|
| `test_mongodb_connection.py` | Core system tests | No | 10s | ⭐ Start here |
| `test_and_keep_data.py` | Upload & keep data | No | 15s | ⭐ For inspection |
| `inspect_database.py` | View database contents | No | 5s | After upload |
| `check_openai_status.py` | Check API quota | Yes (minimal) | 5s | Before AI tests |
| `test_complete_workflow.py` | Full workflow + AI | Yes | 2min | If you have credits |

---

## 🚀 Step-by-Step Testing

### Prerequisites

Before starting, ensure:
- ✅ Python virtual environment is activated
- ✅ MongoDB is running
- ✅ You're in the tests directory

```bash
# Activate virtual environment
cd C:\Master-Projects\pdf-processor\pdf-processor
..\venv\Scripts\activate

# Check MongoDB is running
# (You should see MongoDB service running)

# Navigate to tests
cd tests
```

---

### Step 1: Test Core System (No API Calls)

**File:** `test_mongodb_connection.py`

**What it tests:**
- ✓ All Python packages installed
- ✓ MongoDB connection
- ✓ Database initialization
- ✓ GridFS file storage
- ✓ PDF text extraction
- ✓ Complete data workflow

**Run:**
```bash
python test_mongodb_connection.py
```

**Expected output:**
```
======================================================================
Test Summary
======================================================================
Imports                   PASSED ✓
MongoDB                   PASSED ✓
DB Manager                PASSED ✓
GridFS                    PASSED ✓
PDF Processing            PASSED ✓
Workflow                  PASSED ✓
Indexes                   PASSED ✓
OpenAI                    PASSED ✓

Results: 8 passed, 0 failed, 0 skipped
✓ All tests passed! System is ready to use.
```

**If all tests pass:** ✅ Your core system is working perfectly!

**If tests fail:** See troubleshooting section below.

---

### Step 2: Upload Test Data (Keep in Database)

**File:** `test_and_keep_data.py`

**What it does:**
- Uploads German PDF to MongoDB
- Stores original in GridFS
- Saves all pages
- Tests search functionality
- **Does NOT delete** data (keeps for inspection)

**Run:**
```bash
python test_and_keep_data.py
```

**Expected output:**
```
PDF Upload Test - Data Will Be Kept
================================================================================

✓ Step 1: Extracting text from PDF...
  Extracted 84 pages

✓ Step 2: Saving to MongoDB with GridFS...
  Document saved with ID: a73069c4-f896-43d7-ba27-54355bd05898

✓ Step 3: Verifying data in MongoDB...
  Document found in 'documents' collection
  Found 84 pages in 'pages' collection

✓ Step 4: Testing search functionality...
  Search found 5 results

✓ Step 5: Inspect data in MongoDB
  [Shows MongoDB inspection commands]

Data has been KEPT in database for inspection!
Document ID: a73069c4-f896-43d7-ba27-54355bd05898
```

**Result:** ✅ Test data is now in MongoDB for inspection

---

### Step 3: Inspect Database Contents

**File:** `inspect_database.py`

**What it shows:**
- Number of documents in each collection
- Document metadata
- Sample pages
- GridFS files
- Search results

**Run:**
```bash
python inspect_database.py
```

**Expected output:**
```
MongoDB Database Inspector
================================================================================

COLLECTION COUNTS
================================================================================
documents collection:  1 documents
pages collection:      84 pages
fs.files (GridFS):     1 files
fs.chunks (GridFS):    8 chunks

DOCUMENTS
================================================================================
Document 1:
  doc_id:           a73069c4-f896-43d7-ba27-54355bd05898
  filename:         Leitfaden-Genehmigungsverfahren-2020.pdf
  total_pages:      84
  pdf_file_id:      6970a7d0a72879450745f677
  status:           raw
  summary:          (not generated yet)
  keywords:         (not generated yet)

SAMPLE PAGES (first 3)
================================================================================
Page 1:
  text_length:      88 characters
  status:           raw
  text_sample:      Genehmigungs- und Anzeigeverfahren...

GRIDFS FILES
================================================================================
GridFS File 1:
  _id:              6970a7d0a72879450745f677
  filename:         Leitfaden-Genehmigungsverfahren-2020.pdf
  length:           1.89 MB

SEARCH TEST
================================================================================
Search for 'Genehmigung': 3 results
Result 1:
  filename:         Leitfaden-Genehmigungsverfahren-2020.pdf
  page_num:         13
  search_score:     1.04
```

**What this confirms:**
- ✅ PDF is stored in GridFS
- ✅ All pages are in pages collection
- ✅ Document metadata is correct
- ✅ Search is working (German keywords found!)

---

### Step 4: Check OpenAI API Status (Optional)

**File:** `check_openai_status.py`

**What it checks:**
- OpenAI API key validity
- Available quota
- Account status

**Run:**
```bash
python check_openai_status.py
```

**Possible outputs:**

**A) If you have credits:**
```
✓ API Key found
✓ API connection successful!
✓ API key is valid and has available quota
```

**B) If quota exceeded (current situation):**
```
✓ API Key found
✗ Rate limit exceeded
⚠ Your account has insufficient quota

Solutions:
  1. Check usage: https://platform.openai.com/usage
  2. Add credits: https://platform.openai.com/account/billing
```

---

### Step 5: Full Workflow Test (Optional - Uses OpenAI)

**File:** `test_complete_workflow.py`

**⚠️ Warning:** This test uses OpenAI API and costs ~$0.02-0.05

**What it tests:**
- Everything from Steps 1-2
- AI processing (summaries + keywords) for 3 pages
- Complete cleanup after test

**Run:**
```bash
python test_complete_workflow.py
```

**Expected output:**
```
Total: 18/20 tests passed (90%)

✓ Environment Configuration        3/3 PASSED
✓ PDF Text Extraction              2/2 PASSED
✓ Database Operations              5/5 PASSED
✗ AI Processing                    0/2 FAILED (if no credits)
✓ Keyword Search                   1/1 PASSED
✓ PDF Download                     1/1 PASSED
✓ Document Status                  2/2 PASSED
✓ Structured Data                  1/1 PASSED
✓ Cleanup                          2/2 PASSED
```

**Note:** AI tests may fail if OpenAI quota is exceeded. This is expected.

---

## 📊 Understanding Test Results

### What "18/20 tests passed" means:

**✅ 18 PASSED (Core Features - 100% Working):**
1. Environment configuration (3 tests)
2. PDF extraction (2 tests)
3. Database operations (5 tests)
4. Search functionality (1 test)
5. PDF download (1 test)
6. Document status (2 tests)
7. Structured data (1 test)
8. Cleanup (2 tests)
9. All import checks (1 test)

**⚠️ 2 FAILED (AI Features - Needs OpenAI Credits):**
1. AI summary generation
2. AI keyword extraction

### Why AI tests fail:

**Error:** `insufficient_quota`

**Reason:** OpenAI account has no available credits

**Impact:** 
- ✅ System still works perfectly
- ✅ Search works (uses raw text)
- ⚠️ AI summaries not generated

---

## 🎯 Quick Testing Workflow

### For Students (Recommended Path):

```bash
# 1. Test core system (fast, free)
python test_mongodb_connection.py
# Result: Should show 8/8 passed

# 2. Upload test data (fast, free)
python test_and_keep_data.py
# Result: Data saved to MongoDB

# 3. Inspect what was saved (fast, free)
python inspect_database.py
# Result: Shows all data in database

# 4. Check API status (optional)
python check_openai_status.py
# Result: Shows if OpenAI credits available

# 5. If you have credits, run full test
python test_complete_workflow.py
# Result: Tests AI features (uses credits)
```

**Time required:** 2-3 minutes for steps 1-3 (no cost)

---

## 🔍 What Each Test Verifies

### test_mongodb_connection.py ✅

**Verifies:**
- MongoDB connection works
- Collections can be created
- Indexes are working
- GridFS can store/retrieve files
- PDF text extraction works

**Does NOT verify:**
- AI processing (no API calls)
- Actual data persistence (cleans up after test)

---

### test_and_keep_data.py ✅

**Verifies:**
- Complete upload workflow
- Data persistence in MongoDB
- GridFS storage
- Search functionality

**Does NOT verify:**
- AI processing (no API calls)

**Important:** Keeps data for inspection!

---

### inspect_database.py ✅

**Shows you:**
- How many documents in database
- How many pages stored
- GridFS file details
- Sample page content
- Search test results

**Use this to:** Verify data is actually in MongoDB

---

### check_openai_status.py ⚠️

**Checks:**
- API key configuration
- API key validity
- Available quota

**Uses:** One minimal API call (~$0.001)

**Use this to:** Diagnose OpenAI issues before running full tests

---

### test_complete_workflow.py ⚠️

**Verifies:**
- Everything above
- AI processing (summaries + keywords)
- Complete workflow end-to-end

**Uses:** OpenAI API for 3 pages (~$0.02-0.05)

**Cleans up:** Deletes test data after completion

---

## 🐛 Troubleshooting

### Problem: "MongoDB connection failed"

**Solution:**
```bash
# Check if MongoDB service is running
# Windows: Check Services app
# Linux: sudo systemctl status mongodb
# Mac: brew services list
```

### Problem: "Module not found"

**Solution:**
```bash
# Make sure venv is activated
..\venv\Scripts\activate

# Reinstall dependencies
pip install -r ../requirements.txt
```

### Problem: "Test PDF not found"

**Solution:**
```bash
# Check if PDF exists
ls ../uploads/Leitfaden-Genehmigungsverfahren-2020.pdf

# If not, place a test PDF there
```

### Problem: "OpenAI rate limit exceeded"

**This is expected if:**
- Free $5 credit was used
- Free trial expired (3 months)
- No payment method added

**Solution:**
- Visit: https://platform.openai.com/account/billing
- Add credits ($5-10 recommended)

**Alternative:**
- Use system without AI (works perfectly!)
- Only summaries will be missing

---

## ✅ Success Criteria

After running tests, you should see:

### Minimum (Core Features):
- ✅ test_mongodb_connection.py: 8/8 tests passed
- ✅ MongoDB has data (check with inspect_database.py)
- ✅ Search returns results

### With OpenAI Credits:
- ✅ Above tests passed
- ✅ test_complete_workflow.py: 20/20 tests passed
- ✅ AI summaries generated

---

## 🎓 For Teachers/Instructors

### Teaching Sequence:

**Lesson 1: Core System**
1. Run `test_mongodb_connection.py`
2. Explain each test component
3. Show that system works without AI

**Lesson 2: Data Persistence**
1. Run `test_and_keep_data.py`
2. Run `inspect_database.py`
3. Show actual data in MongoDB
4. Demonstrate search functionality

**Lesson 3: AI Integration (Optional)**
1. Run `check_openai_status.py`
2. Discuss API costs and quotas
3. If credits available: run `test_complete_workflow.py`
4. Show difference with/without AI

**Lesson 4: Web Interface**
1. Start application: `python app.py`
2. Upload PDFs via web interface
3. Test search functionality
4. Download original PDFs

---

## 📝 Quick Reference

```bash
# Setup (once)
cd C:\Master-Projects\pdf-processor\pdf-processor
..\venv\Scripts\activate
cd tests

# Run tests (in order)
python test_mongodb_connection.py      # Test 1: Core (free)
python test_and_keep_data.py           # Test 2: Upload (free)
python inspect_database.py             # Test 3: Inspect (free)
python check_openai_status.py          # Test 4: API check (minimal cost)
python test_complete_workflow.py       # Test 5: Full test (uses API)

# Start application
cd ..
python app.py
```

---

## 🎯 Key Takeaways

1. **System works without OpenAI** - Core features fully functional
2. **Search doesn't need AI** - Uses raw extracted text
3. **AI is optional enhancement** - Adds summaries and keywords
4. **Data persistence verified** - MongoDB stores everything correctly
5. **GridFS works perfectly** - Large PDFs handled automatically

---

## 📞 Getting Help

**If tests fail:**
1. Read the error message carefully
2. Check troubleshooting section above
3. Verify prerequisites (MongoDB running, venv activated)
4. Run `inspect_database.py` to see current state

**If OpenAI fails:**
1. Run `check_openai_status.py` to diagnose
2. Check account at: https://platform.openai.com/usage
3. Remember: System works without AI

---

**Happy Testing! 🚀**

