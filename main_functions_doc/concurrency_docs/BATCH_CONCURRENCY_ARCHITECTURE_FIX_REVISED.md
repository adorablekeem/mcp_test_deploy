# Batch Concurrency Architecture - Revised Fix for SSL and Segfault Issues

## 🚨 **Critical Issues Identified from Production Logs**

### **Error Analysis from Production:**
```
[SSL] record layer failure (_ssl.c:2559)
Invalid requests[0].replaceAllText: This request cannot be applied
segmentation fault /Users/.../python
```

### **Root Causes:**
1. **Connection Pool Exhaustion**: Too many concurrent SSL connections to Google APIs
2. **Google Slides API Race Conditions**: Multiple concurrent requests modifying same presentation
3. **Memory Corruption**: Concurrent operations overwhelming Python/asyncio resources
4. **API Rate Limiting**: Google Slides API rejecting concurrent modification requests

## 🔄 **Revised Architecture Strategy**

### **Problem with Current Approach:**
```python
# CURRENT (PROBLEMATIC): Slide-level concurrency
async def concurrent_batch_text_replace():
    # Process multiple slides simultaneously
    slide_tasks = [process_slide_text(slide_id) for slide_id in slides]  # ← PROBLEM
    results = await asyncio.gather(*slide_tasks)  # ← Multiple concurrent API calls
```

**Issues:**
- Multiple simultaneous `batchUpdate()` calls to same presentation
- Each slide creates separate HTTP connections
- No coordination between concurrent operations
- Google Slides API conflicts when multiple requests modify same presentation

### **Corrected Architecture:**

#### **Strategy 1: Sequential Slides with Concurrent Operations (RECOMMENDED)**
```python
# BETTER: Process slides sequentially but batch operations within each slide
async def improved_batch_text_replace():
    for slide in slides:  # ← Sequential slide processing
        # Concurrent operations WITHIN each slide only
        await process_slide_operations_concurrent(slide)
```

#### **Strategy 2: Semaphore-Limited Slide Processing**
```python
# ALTERNATIVE: Very limited slide concurrency with proper coordination
async def semaphore_limited_batch_replace():
    semaphore = asyncio.Semaphore(1)  # ← Only 1 slide at a time initially
    slide_tasks = [process_slide_with_semaphore(slide, semaphore) for slide in slides]
    results = await asyncio.gather(*slide_tasks)
```

## 🎯 **New Implementation Plan**

### **Phase 1: Conservative Fix (Immediate - This Week)**

**Goal**: Eliminate SSL/segfault issues while maintaining some performance improvement

**Changes:**
1. **Reduce concurrency to 1 slide at a time** (eliminate race conditions)
2. **Implement proper connection reuse** (fix SSL issues)
3. **Add request batching within slides** (maintain some performance gain)
4. **Add circuit breaker pattern** (automatic fallback on failures)

```python
async def safe_batch_text_replace(
    slides_service,
    presentation_id: str,
    text_map: Dict[str, str],
    max_concurrent_slides: int = 1  # ← Conservative start
):
    # Process slides one at a time to avoid API conflicts
    results = []
    for i, slide in enumerate(slides):
        try:
            # Add small delay between slides to prevent API overload
            if i > 0:
                await asyncio.sleep(0.5)
            
            result = await process_slide_with_connection_reuse(
                slides_service, presentation_id, slide['objectId'], text_map
            )
            results.append(result)
            
        except Exception as e:
            logger.error(f"Slide {i} failed: {e}")
            # Continue processing other slides
            results.append({"success": False, "error": str(e)})
    
    return aggregate_results(results)
```

### **Phase 2: Gradual Concurrency Increase (Next Week)**

**Goal**: Carefully increase concurrency with proper safeguards

**Changes:**
1. **Increase to max 2 concurrent slides** with proper coordination
2. **Implement presentation-level locking** to prevent conflicts  
3. **Add comprehensive monitoring** for success rates
4. **Implement adaptive concurrency** (reduce on errors, increase on success)

### **Phase 3: Advanced Optimization (Future)**

**Goal**: Optimal performance with full reliability

**Changes:**
1. **Smart batching across slides** (group compatible operations)
2. **Connection pooling management** (reuse HTTP connections)
3. **Predictive rate limiting** (adapt to Google API patterns)

## 🛠️ **Immediate Fixes Required**

### **1. Fix Connection Pooling Issues**
```python
# Current problematic pattern:
async def process_slide():
    # Each call creates new HTTP connection
    await slides_service.presentations().batchUpdate().execute()  # ← New connection each time

# Fixed pattern:
class GoogleSlidesConnectionManager:
    def __init__(self):
        self.service = self._create_service_with_connection_pooling()
    
    def _create_service_with_connection_pooling(self):
        # Configure HTTP connection pooling
        from googleapiclient.http import build_http
        http = build_http()
        http.connections = {'https': {'pool_connections': 1, 'pool_maxsize': 5}}
        return build('slides', 'v1', http=http)

# Global connection manager (singleton pattern)
connection_manager = GoogleSlidesConnectionManager()
```

### **2. Fix Race Condition Issues**
```python
# Add presentation-level coordination
class PresentationLock:
    def __init__(self):
        self._locks = {}
    
    async def acquire(self, presentation_id: str):
        if presentation_id not in self._locks:
            self._locks[presentation_id] = asyncio.Lock()
        return await self._locks[presentation_id].acquire()

presentation_locks = PresentationLock()

async def process_slide_safe(presentation_id, slide_id):
    async with presentation_locks.acquire(presentation_id):
        # Only one operation per presentation at a time
        return await actual_slide_processing(presentation_id, slide_id)
```

### **3. Add Circuit Breaker Pattern**
```python
class BatchOperationCircuitBreaker:
    def __init__(self, failure_threshold=3, reset_timeout=60):
        self.failure_count = 0
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.last_failure_time = 0
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
    
    async def call_with_circuit_breaker(self, func, *args, **kwargs):
        if self.state == "OPEN":
            if time.time() - self.last_failure_time > self.reset_timeout:
                self.state = "HALF_OPEN"
            else:
                raise Exception("Circuit breaker is OPEN - falling back to sequential")
        
        try:
            result = await func(*args, **kwargs)
            if self.state == "HALF_OPEN":
                self.state = "CLOSED"
                self.failure_count = 0
            return result
        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = time.time()
            if self.failure_count >= self.failure_threshold:
                self.state = "OPEN"
            raise

circuit_breaker = BatchOperationCircuitBreaker()
```

## 🔧 **Configuration Changes**

### **Updated Environment Variables:**
```bash
# EMERGENCY: Disable all concurrency until fixed
export SCALAPAY_ENABLE_CONCURRENT_BATCH_OPERATIONS=false

# When re-enabling, start conservatively:
export SCALAPAY_MAX_CONCURRENT_SLIDES=1  # Start with 1, gradually increase
export SCALAPAY_SLIDES_API_BATCH_SIZE=3  # Smaller batches
export SCALAPAY_BATCH_RETRY_ATTEMPTS=1   # Fewer retries to prevent buildup
export SCALAPAY_BATCH_RETRY_DELAY=2.0    # Longer delays between retries

# Circuit breaker settings:
export SCALAPAY_CIRCUIT_BREAKER_THRESHOLD=2
export SCALAPAY_CIRCUIT_BREAKER_TIMEOUT=30

# Connection management:
export SCALAPAY_HTTP_CONNECTION_POOL_SIZE=3
export SCALAPAY_HTTP_CONNECTION_TIMEOUT=30
```

## 🎯 **Success Metrics for Fix**

### **Primary Goals (Must Achieve):**
1. **Zero SSL record layer failures**
2. **Zero segmentation faults**
3. **Zero Google Slides API "cannot be applied" errors**
4. **100% operation completion** (no hanging processes)

### **Secondary Goals (Nice to Have):**
1. **At least 2x performance improvement** over pure sequential
2. **>95% individual slide success rate**
3. **<5% circuit breaker activation rate**

## 📋 **Implementation Checklist**

### **Week 1 (Emergency Fix):**
- [ ] Implement `GoogleSlidesConnectionManager` for connection pooling
- [ ] Add `PresentationLock` to prevent race conditions  
- [ ] Implement `BatchOperationCircuitBreaker` with automatic fallback
- [ ] Set `max_concurrent_slides=1` as default
- [ ] Add comprehensive error logging and monitoring
- [ ] Test with problematic presentation that caused segfault

### **Week 2 (Gradual Improvement):**
- [ ] Gradually increase `max_concurrent_slides` to 2, monitor for issues
- [ ] Implement adaptive concurrency (reduce on errors)
- [ ] Add presentation-level operation batching
- [ ] Performance testing and optimization

### **Week 3 (Production Deployment):**
- [ ] Deploy with conservative settings
- [ ] Monitor production metrics for 1 week
- [ ] Gradually increase concurrency based on success rates

---

**Key Insight**: The current concurrent implementation is too aggressive. We need to prioritize **reliability over performance** and gradually increase concurrency only after proving stability at each level.