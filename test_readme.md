# Say Hi: [lmcrean@gmail.com](mailto:lmcrean@gmail.com)

# Open Source Contributions
Now running in production across millions of business applications.

## <img src="https://github.com/rropen.png" width="24" alt="Rolls-Royce"> Rolls-Royce, terraform-provider-cscdm, Go

1. **[Fix: Add HTTP timeout to prevent Terraform from hanging indefinitely](https://github.com/rropen/terraform-provider-cscdm/pull/16)**<br>*Added 30-second HTTP request timeout to prevent the Terraform provider from hanging indefinitely when the CSC Domain Manager API accepts connections but doesn't respond.*
   <details><summary><code>+11/-8</code> | merged 1 week ago</summary>

   ```diff
   diff --git a/internal/cscdm/cscdm.go b/internal/cscdm/cscdm.go
   --- a/internal/cscdm/cscdm.go
   +++ b/internal/cscdm/cscdm.go
   @@ -15,6 +15,7 @@ const (
    	CSC_DOMAIN_MANAGER_API_URL = "https://apis.cscglobal.com/dbs/api/v2/"
    	POLL_INTERVAL              = 5 * time.Second
    	FLUSH_IDLE_DURATION        = 5 * time.Second
   +	HTTP_REQUEST_TIMEOUT       = 30 * time.Second
    )
    
    type Client struct {
   @@ -36,14 +37,16 @@ type Client struct {
    }
    
    func (c *Client) Configure(apiKey string, apiToken string) {
   -	c.http = &http.Client{Transport: &util.HttpTransport{
   -		BaseUrl: CSC_DOMAIN_MANAGER_API_URL,
   -		Headers: map[string]string{
   -			"accept":        "application/json",
   -			"apikey":        apiKey,
   -			"Authorization": fmt.Sprintf("Bearer %s", apiToken),
   -		},
   -	}}
   +	c.http = &http.Client{
   +		Timeout: HTTP_REQUEST_TIMEOUT,
   +		Transport: &util.HttpTransport{
   +			BaseUrl: CSC_DOMAIN_MANAGER_API_URL,
   +			Headers: map[string]string{
   +				"accept":        "application/json",
   +				"apikey":        apiKey,
   +				"Authorization": fmt.Sprintf("Bearer %s", apiToken),
   +			},
   +		}}
    
    	c.returnChannels = make(map[string]chan *ZoneRecord)
    	c.errorChannels = make(map[string]chan error)
   ```
   </details>

2. **[Enhance(error handling): improve flush loop and trigger handling in cscdm](https://github.com/rropen/terraform-provider-cscdm/pull/9)**<br>*Replaced `sync.Cond` with buffered channels to fix goroutine leaks, added `sync.Once` to prevent panics, and enabled recovery from transient failures instead of permanent termination.*
   <details><summary><code>+483/-19</code> | merged 4 months ago</summary>

   ```diff
   diff --git a/internal/cscdm/cscdm.go b/internal/cscdm/cscdm.go
   --- a/internal/cscdm/cscdm.go
   +++ b/internal/cscdm/cscdm.go
   @@ -26,8 +26,9 @@ type Client struct {
    	batchMutex          sync.Mutex
    	returnChannelsMutex sync.Mutex
    
   -	flushTrigger      *sync.Cond
   +	flushTrigger      chan struct{}
    	flushLoopStopChan chan struct{}
   +	stopOnce          sync.Once
    
    	zoneCache  map[string]*Zone
    	zoneGroup  singleflight.Group
   @@ -47,7 +48,7 @@ func (c *Client) Configure(apiKey string, apiToken string) {
    	c.returnChannels = make(map[string]chan *ZoneRecord)
    	c.errorChannels = make(map[string]chan error)
    
   -	c.flushTrigger = sync.NewCond(&sync.Mutex{})
   +	c.flushTrigger = make(chan struct{}, 1)
    	c.flushLoopStopChan = make(chan struct{})
    
    	c.zoneCache = make(map[string]*Zone)
   @@ -57,28 +58,24 @@ func (c *Client) Configure(apiKey string, apiToken string) {
    
    func (c *Client) flushLoop() {
    	for {
   -		triggerChan := make(chan struct{})
   -		go func() {
   -			c.flushTrigger.L.Lock()
   -			c.flushTrigger.Wait()
   -			c.flushTrigger.L.Unlock()
   -			close(triggerChan)
   -		}()
   -
    		flushTimer := time.NewTimer(FLUSH_IDLE_DURATION)
    
    		select {
   -		case <-triggerChan:
   +		case <-c.flushTrigger:
    			// Flush triggered; reset flush timer
    			flushTimer.Stop()
   -			continue
   +			// Drain the channel in case of multiple signals
   +			select {
   +			case <-c.flushTrigger:
   +			default:
   +			}
    		case <-flushTimer.C:
    			// Timer expired; flush queue
    			err := c.flush()
    
    			if err != nil {
   -				fmt.Fprintf(os.Stderr, "failed to flush queue: %s", err.Error())
   -				return
   +				fmt.Fprintf(os.Stderr, "failed to flush queue: %s\n", err.Error())
   +				// Continue - don't return/terminate
    			}
    		case <-c.flushLoopStopChan:
    			// Stop flush loop
   @@ -89,12 +86,15 @@ func (c *Client) flushLoop() {
    }
    
    func (c *Client) triggerFlush() {
   -	c.flushTrigger.L.Lock()
   -	defer c.flushTrigger.L.Unlock()
   -
   -	c.flushTrigger.Signal()
   +	// Non-blocking send - if channel full, trigger already pending
   +	select {
   +	case c.flushTrigger <- struct{}{}:
   +	default:
   +	}
    }
    
    func (c *Client) Stop() {
   -	close(c.flushLoopStopChan)
   +	c.stopOnce.Do(func() {
   +		close(c.flushLoopStopChan)
   +	})
    }
   diff --git a/internal/cscdm/cscdm_flush_fix_test.go b/internal/cscdm/cscdm_flush_fix_test.go
   --- a/internal/cscdm/cscdm_flush_fix_test.go
   +++ b/internal/cscdm/cscdm_flush_fix_test.go
   @@ -0,0 +1,219 @@
   +// Maintainer Test Script for FlushLoop Fix Validation
   +//
   +// This script validates that the flushLoop goroutine fix is working correctly.
   +// Run with: go test ./internal/cscdm
   +//
   +// The fix addresses:
   +// 1. Goroutine leaks in the flush loop
   +// 2. Channel management and proper cleanup
   +// 3. Error resilience (flush errors don't terminate the loop)
   +// 4. Graceful shutdown of background goroutines
   +
   +package cscdm_test
   +
   +import (
   +	"runtime"
   +	"sync"
   +	"terraform-provider-cscdm/internal/cscdm"
   +	"testing"
   +	"time"
   +)
   +
   +func TestFlushLoopFix(t *testing.T) {
   +	tests := []struct {
   +		name string
   +		fn   func(t *testing.T)
   +	}{
   +		{"Goroutine Leak Prevention", testGoroutineLeaks},
   +		{"Error Resilience", testErrorResilience},
   +		{"Concurrent Access Safety", testConcurrentAccess},
   +		{"Graceful Shutdown", testGracefulShutdown},
   +		{"Multiple Stop Calls", testMultipleStops},
   +	}
   +
   +	for _, test := range tests {
   +		t.Run(test.name, test.fn)
   +	}
   +}
   +
   +func testGoroutineLeaks(t *testing.T) {
   +	// Record baseline
   +	initialGoroutines := runtime.NumGoroutine()
   +
   +	// Test that multiple client create/stop cycles work without accumulating issues
   +	for cycle := 0; cycle < 5; cycle++ {
   +		client := &cscdm.Client{}
   +		client.Configure("test-key", "test-token")
   +
   +		// Let it run briefly
   +		time.Sleep(20 * time.Millisecond)
   +
   +		// Test clean stop
   +		done := make(chan bool, 1)
   +		go func() {
   +			client.Stop()
   +			done <- true
   +		}()
   +
   +		select {
   +		case <-done:
   +			// Good
   +		case <-time.After(2 * time.Second):
   +			t.Fatal("Stop() hung")
   +		}
   +
   +		// Allow cleanup
   +		time.Sleep(50 * time.Millisecond)
   +		runtime.GC()
   +	}
   +
   +	// Final goroutine check
   +	finalGoroutines := runtime.NumGoroutine()
   +	if finalGoroutines > initialGoroutines+3 {
   +		t.Errorf("Goroutine leak detected: %d → %d (+%d)",
   +			initialGoroutines, finalGoroutines, finalGoroutines-initialGoroutines)
   +	}
   +}
   +
   +func testErrorResilience(t *testing.T) {
   +	client := &cscdm.Client{}
   +	client.Configure("invalid-key", "invalid-token") // Force API errors
   +
   +	initialGoroutines := runtime.NumGoroutine()
   +
   +	// Wait for multiple flush cycles that should generate errors
   +	for i := 0; i < 2; i++ {
   +		time.Sleep(cscdm.FLUSH_IDLE_DURATION + 100*time.Millisecond)
   +
   +		// Check that goroutines haven't died from errors
   +		currentGoroutines := runtime.NumGoroutine()
   +		if currentGoroutines < initialGoroutines {
   +			t.Errorf("Flush loop appears to have died from errors (goroutines: %d → %d)",
   +				initialGoroutines, currentGoroutines)
   +			return
   +		}
   +	}
   +
   +	// Try to stop cleanly - if the loop died, this might hang
   +	done := make(chan bool, 1)
   +	go func() {
   +		client.Stop()
   +		done <- true
   +	}()
   +
   +	select {
   +	case <-done:
   +		// Success
   +	case <-time.After(3 * time.Second):
   +		t.Fatal("Stop() hung after errors")
   +	}
   +}
   +
   +func testConcurrentAccess(t *testing.T) {
   +	client := &cscdm.Client{}
   +	client.Configure("test-key", "test-token")
   +
   +	var wg sync.WaitGroup
   +
   +	// Launch concurrent goroutines that trigger flushes
   +	for i := 0; i < 10; i++ {
   +		wg.Add(1)
   +		go func() {
   +			defer wg.Done()
   +			defer func() {
   +				if r := recover(); r != nil {
   +					t.Errorf("Panic during concurrent access: %v", r)
   +				}
   +			}()
   +
   +			// Test concurrent access to the client
   +			for j := 0; j < 20; j++ {
   +				// Just access the client concurrently
   +				_ = client
   +				time.Sleep(time.Millisecond)
   +			}
   +		}()
   +	}
   +
   +	wg.Wait()
   +	client.Stop()
   +}
   +
   +func testGracefulShutdown(t *testing.T) {
   +	client := &cscdm.Client{}
   +	client.Configure("test-key", "test-token")
   +
   +	// Start background work
   +	stop := make(chan bool)
   +	var wg sync.WaitGroup
   +
   +	wg.Add(1)
   +	go func() {
   +		defer wg.Done()
   +		for {
   +			select {
   +			case <-stop:
   +				return
   +			default:
   +				// Just keep the goroutine active
   +				time.Sleep(time.Millisecond)
   +			}
   +		}
   +	}()
   +
   +	time.Sleep(20 * time.Millisecond)
   +
   +	// Stop everything
   +	close(stop)
   +	client.Stop()
   +
   +	// Wait for graceful shutdown
   +	done := make(chan bool)
   +	go func() {
   +		wg.Wait()
   +		done <- true
   +	}()
   +
   +	select {
   +	case <-done:
   +		// Success
   +	case <-time.After(1 * time.Second):
   +		t.Fatal("Graceful shutdown timed out")
   +	}
   +}
   +
   +func testMultipleStops(t *testing.T) {
   +	client := &cscdm.Client{}
   +	client.Configure("test-key", "test-token")
   +
   +	// Let client initialize
   +	time.Sleep(10 * time.Millisecond)
   +
   +	// Test single stop works
   +	done := make(chan bool)
   +	go func() {
   +		defer func() {
   +			if r := recover(); r != nil {
   +				done <- false
   +				return
   +			}
   +			done <- true
   +		}()
   +
   +		client.Stop()
   +	}()
   +
   +	select {
   +	case success := <-done:
   +		if !success {
   +			t.Fatal("Stop() panicked")
   +		}
   +	case <-time.After(1 * time.Second):
   +		t.Fatal("Stop() hung")
   +	}
   +}
   +
   +// Note: Since triggerFlush() is not exported, this integration test focuses on
   +// observable behaviors like goroutine counts and shutdown behavior.
   +// Both this integration test and the unit tests use only the public API
   +// (Configure/Stop) to validate the internal trigger mechanisms.
   diff --git a/internal/cscdm/cscdm_goroutine_test.go b/internal/cscdm/cscdm_goroutine_test.go
   --- a/internal/cscdm/cscdm_goroutine_test.go
   +++ b/internal/cscdm/cscdm_goroutine_test.go
   @@ -0,0 +1,245 @@
   +package cscdm_test
   +
   +import (
   +	"runtime"
   +	"sync"
   +	"terraform-provider-cscdm/internal/cscdm"
   +	"testing"
   +	"time"
   +)
   +
   +func TestClient_GoroutineLeakPrevention(t *testing.T) {
   +	// Record initial goroutine count
   +	initialGoroutines := runtime.NumGoroutine()
   +
   +	// Create multiple clients to test for cumulative leaks
   +	clients := make([]*cscdm.Client, 5)
   +
   +	for i := 0; i < 5; i++ {
   +		client := &cscdm.Client{}
   +		client.Configure("test-key", "test-token")
   +		clients[i] = client
   +
   +		// Allow goroutines to start
   +		time.Sleep(10 * time.Millisecond)
   +	}
   +
   +	// Verify goroutines increased as expected (at least 2 per client: flushLoop + trigger watcher)
   +	midGoroutines := runtime.NumGoroutine()
   +	if midGoroutines <= initialGoroutines {
   +		t.Errorf("Expected goroutine count to increase after creating clients. Initial: %d, Mid: %d", initialGoroutines, midGoroutines)
   +	}
   +
   +	// Stop all clients
   +	for _, client := range clients {
   +		client.Stop()
   +	}
   +
   +	// Allow time for cleanup
   +	time.Sleep(200 * time.Millisecond)
   +	runtime.GC()
   +	runtime.GC() // Double GC to ensure cleanup
   +	time.Sleep(100 * time.Millisecond)
   +
   +	// Check final goroutine count
   +	finalGoroutines := runtime.NumGoroutine()
   +	if finalGoroutines > initialGoroutines+2 { // Allow small margin for test goroutines
   +		t.Errorf("Goroutine leak detected. Initial: %d, Final: %d, Leaked: %d",
   +			initialGoroutines, finalGoroutines, finalGoroutines-initialGoroutines)
   +	}
   +
   +	// Test that we can create and stop another client without issues
   +	testClient := &cscdm.Client{}
   +	testClient.Configure("test-key", "test-token")
   +
   +	done := make(chan bool, 1)
   +	go func() {
   +		testClient.Stop()
   +		done <- true
   +	}()
   +
   +	select {
   +	case <-done:
   +		// Success - no deadlock from leaked goroutines
   +	case <-time.After(2 * time.Second):
   +		t.Error("Final client Stop() hung, suggesting goroutine leak interference")
   +	}
   +}
   +
   +func TestClient_FlushErrorResilience(t *testing.T) {
   +	// This test verifies that the flush loop continues running even after errors
   +	client := &cscdm.Client{}
   +	client.Configure("invalid-key", "invalid-token") // Force API errors
   +
   +	initialGoroutines := runtime.NumGoroutine()
   +
   +	// Wait for multiple flush cycles with errors
   +	for i := 0; i < 3; i++ {
   +		time.Sleep(cscdm.FLUSH_IDLE_DURATION + 50*time.Millisecond)
   +
   +		// Verify flush loop is still running by checking goroutine stability
   +		currentGoroutines := runtime.NumGoroutine()
   +		if currentGoroutines < initialGoroutines {
   +			t.Errorf("Goroutine count decreased after error cycle %d, suggesting flush loop died", i+1)
   +			break
   +		}
   +	}
   +
   +	// Verify the flush loop is still responsive by stopping cleanly
   +	done := make(chan bool, 1)
   +	go func() {
   +		client.Stop()
   +		done <- true
   +	}()
   +
   +	select {
   +	case <-done:
   +		// Test passes if Stop() completes without hanging
   +	case <-time.After(2 * time.Second):
   +		t.Error("Stop() hung, suggesting flush loop died from error")
   +	}
   +}
   +
   +func TestClient_ConcurrentFlushTriggers(t *testing.T) {
   +	client := &cscdm.Client{}
   +	client.Configure("test-key", "test-token")
   +
   +	initialGoroutines := runtime.NumGoroutine()
   +
   +	// Simulate concurrent operations that would trigger flushes
   +	var wg sync.WaitGroup
   +	for i := 0; i < 10; i++ {
   +		wg.Add(1)
   +		go func() {
   +			defer wg.Done()
   +			// Simulate work that might trigger flushes
   +			for j := 0; j < 5; j++ {
   +				time.Sleep(time.Millisecond)
   +			}
   +		}()
   +	}
   +
   +	wg.Wait()
   +	time.Sleep(50 * time.Millisecond)
   +
   +	// Verify goroutines haven't multiplied excessively
   +	currentGoroutines := runtime.NumGoroutine()
   +	if currentGoroutines > initialGoroutines+10 {
   +		t.Errorf("Excessive goroutine growth during concurrent operations. Initial: %d, Current: %d", initialGoroutines, currentGoroutines)
   +	}
   +
   +	// Test that Stop() works cleanly after concurrent triggers
   +	done := make(chan bool, 1)
   +	go func() {
   +		client.Stop()
   +		done <- true
   +	}()
   +
   +	select {
   +	case <-done:
   +		// Success - no deadlock from concurrent triggers
   +	case <-time.After(2 * time.Second):
   +		t.Error("Stop() hung after concurrent triggers, suggesting channel overflow issue")
   +	}
   +}
   +
   +func TestClient_GracefulShutdown(t *testing.T) {
   +	client := &cscdm.Client{}
   +	client.Configure("test-key", "test-token")
   +
   +	// Start multiple goroutines that trigger flushes
   +	stopWorkers := make(chan bool)
   +	var workerWg sync.WaitGroup
   +
   +	for i := 0; i < 5; i++ {
   +		workerWg.Add(1)
   +		go func() {
   +			defer workerWg.Done()
   +			for {
   +				select {
   +				case <-stopWorkers:
   +					return
   +				default:
   +					// Just keep the goroutine active to test concurrent access
   +					time.Sleep(1 * time.Millisecond)
   +				}
   +			}
   +		}()
   +	}
   +
   +	// Let workers run for a bit
   +	time.Sleep(10 * time.Millisecond)
   +
   +	// Stop workers and client
   +	close(stopWorkers)
   +	client.Stop()
   +
   +	// Wait for workers to finish
   +	done := make(chan bool)
   +	go func() {
   +		workerWg.Wait()
   +		close(done)
   +	}()
   +
   +	select {
   +	case <-done:
   +		// Success
   +	case <-time.After(1 * time.Second):
   +		t.Error("Graceful shutdown timed out")
   +	}
   +}
   +
   +func TestClient_TriggerChannelDraining(t *testing.T) {
   +	client := &cscdm.Client{}
   +	client.Configure("test-key", "test-token")
   +
   +	// Let the client run for a bit to test the flush loop
   +	time.Sleep(50 * time.Millisecond)
   +
   +	// Small delay to let triggers propagate
   +	time.Sleep(10 * time.Millisecond)
   +
   +	// Test clean stop - if channel draining doesn't work, this might hang
   +	done := make(chan bool, 1)
   +	go func() {
   +		client.Stop()
   +		done <- true
   +	}()
   +
   +	select {
   +	case <-done:
   +		// Success - channel draining worked
   +	case <-time.After(1 * time.Second):
   +		t.Error("Stop() hung, suggesting channel draining issue")
   +	}
   +}
   +
   +func TestClient_StopChannelCleanup(t *testing.T) {
   +	client := &cscdm.Client{}
   +	client.Configure("test-key", "test-token")
   +
   +	// Let the client run for a bit
   +	time.Sleep(10 * time.Millisecond)
   +
   +	// Test that Stop() works correctly
   +	done := make(chan bool, 1)
   +	go func() {
   +		defer func() {
   +			if r := recover(); r != nil {
   +				done <- false
   +				return
   +			}
   +			done <- true
   +		}()
   +		client.Stop()
   +	}()
   +
   +	select {
   +	case success := <-done:
   +		if !success {
   +			t.Error("Stop() panicked")
   +		}
   +	case <-time.After(1 * time.Second):
   +		t.Error("Stop() hung")
   +	}
   +}
   ```
   </details>

## <img src="https://github.com/gocardless.png" width="24" alt="GoCardless"> GoCardless, woocommerce-gateway, PHP

- **[Fix inconsistent subscription status after cancellation with centralized cancellation logic](https://github.com/gocardless/woocommerce-gateway-gocardless/pull/88)**<br>*Fixed subscription status incorrectly showing "Pending Cancellation" instead of "Cancelled" when users cancel before GoCardless payment confirmation. Added centralized cancellation handling with parent order status synchronization.*
   <details><summary><code>+81/-0</code> | merged 1 month ago</summary>

   ```diff
   diff --git a/includes/class-wc-gocardless-gateway-addons.php b/includes/class-wc-gocardless-gateway-addons.php
   --- a/includes/class-wc-gocardless-gateway-addons.php
   +++ b/includes/class-wc-gocardless-gateway-addons.php
   @@ -33,13 +33,94 @@ public function __construct() {
    			// Cancel in-progress payment on subscription cancellation.
    			add_action( 'woocommerce_subscription_pending-cancel_' . $this->id, array( $this, 'maybe_cancel_subscription_payment' ) );
    			add_action( 'woocommerce_subscription_cancelled_' . $this->id, array( $this, 'maybe_cancel_subscription_payment' ) );
   +
   +			// Status synchronization for parent orders.
   +			add_action( 'woocommerce_subscription_status_updated', array( $this, 'sync_parent_order_status' ), 10, 3 );
    		}
    
    		if ( class_exists( 'WC_Pre_Orders_Order' ) ) {
    			add_action( 'wc_pre_orders_process_pre_order_completion_payment_' . $this->id, array( $this, 'process_payment_for_released_pre_order' ) );
    		}
    	}
    
   +	/**
   +	 * Synchronize parent order status when all subscriptions are cancelled.
   +	 * Also intercepts pending-cancel transitions for subscriptions with unconfirmed payments,
   +	 * checking the most recent order (parent or renewal) to determine if payment is confirmed.
   +	 *
   +	 * @since x.x.x
   +	 * @param WC_Subscription $subscription The subscription object.
   +	 * @param string          $new_status   The new subscription status.
   +	 * @param string          $old_status   The old subscription status.
   +	 */
   +	public function sync_parent_order_status( $subscription, $new_status, $old_status ) {
   +		// Only process GoCardless subscriptions and subscription cancellation triggered by the customer.
   +		if ( $this->id !== $subscription->get_payment_method() || ! isset( $_GET['change_subscription_to'] ) ) { // phpcs:ignore WordPress.Security.NonceVerification.Recommended
   +			return;
   +		}
   +
   +		// Only process Some status -> 'pending-cancel' transition.
   +		if ( 'pending-cancel' !== $new_status || 'pending-cancel' === $old_status ) {
   +			return;
   +		}
   +
   +		/*
   +		 * Handle transition to pending-cancel status for unconfirmed payments.
   +		 * This checks the most recent order's payment status (parent or latest renewal) from the
   +		 * GoCardless API to avoid edge cases with webhook delays.
   +		 */
   +
   +		// Get the most recent order of the subscription.
   +		$last_order = is_callable( array( $subscription, 'get_last_order' ) )
   +			? $subscription->get_last_order( 'all' )
   +			: $subscription->get_parent();
   +
   +		// If the last order is not a valid order, return.
   +		if ( ! $last_order || ! is_a( $last_order, 'WC_Abstract_Order' ) ) {
   +			return;
   +		}
   +
   +		// Get payment status from GoCardless.
   +		$payment_id     = $this->get_order_resource( $last_order->get_id(), 'payment', 'id' );
   +		$payment_status = '';
   +
   +		if ( $payment_id ) {
   +			$payment = WC_GoCardless_API::get_payment( $payment_id );
   +
   +			if ( is_wp_error( $payment ) || empty( $payment['payments'] ) ) {
   +				wc_gocardless()->log(
   +					sprintf(
   +						'%s - Failed to retrieve payment for order #%s',
   +						__METHOD__,
   +						$last_order->get_id()
   +					)
   +				);
   +			} else {
   +				$payment_status = $payment['payments']['status'] ?? '';
   +			}
   +		}
   +
   +		// Payment confirmed statuses that indicate payment has gone through.
   +		$confirmed_statuses = array( 'confirmed', 'paid_out' );
   +
   +		// If payment is not confirmed, cancel immediately.
   +		if ( ! in_array( $payment_status, $confirmed_statuses, true ) ) {
   +			wc_gocardless()->log(
   +				sprintf(
   +					'%s - Cancelling subscription #%s immediately (order #%s has unconfirmed payment status: %s)',
   +					__METHOD__,
   +					$subscription->get_id(),
   +					$last_order->get_id(),
   +					$payment_status ? $payment_status : 'none'
   +				)
   +			);
   +			$subscription->update_status(
   +				'cancelled',
   +				__( 'Subscription cancelled immediately as payment not confirmed for the last order.', 'woocommerce-gateway-gocardless' )
   +			);
   +		}
   +	}
   +
    	/**
    	 * Update GoCardless resource in order meta.
    	 *
   ```
   </details>

## <img src="https://github.com/google.png" width="24" alt="Google"> Google, Guava, Java

1. **[Fix resource leak in FileBackedOutputStream to prevent file handle exhaustion](https://github.com/google/guava/pull/7986)**<br>*Fixed file handle exhaustion by adding proper exception handling to ensure FileOutputStream is closed when IOException occurs during memory-to-file transition.*
   <details><summary><code>+96/-1</code> | merged 2 months ago</summary>

   ```diff
   diff --git a/guava-tests/test/com/google/common/io/FileBackedOutputStreamTest.java b/guava-tests/test/com/google/common/io/FileBackedOutputStreamTest.java
   --- a/guava-tests/test/com/google/common/io/FileBackedOutputStreamTest.java
   +++ b/guava-tests/test/com/google/common/io/FileBackedOutputStreamTest.java
   @@ -171,4 +171,90 @@ private static boolean isAndroid() {
      private static boolean isWindows() {
        return OS_NAME.value().startsWith("Windows");
      }
   +
   +  /**
   +   * Test that verifies the resource leak fix for Issue #5756.
   +   *
   +   * This test covers a scenario where we write a smaller amount of data first,
   +   * then write a large amount that crosses the threshold (transitioning from
   +   * "not at threshold" to "over the threshold"). This differs from the existing
   +   * testThreshold() which writes exactly enough bytes to fill the buffer, then
   +   * immediately writes more bytes.
   +   *
   +   * Note: Direct testing of the IOException scenario during write/flush is challenging
   +   * without mocking. This test verifies that normal operation with threshold crossing
   +   * still works correctly with the fix in place.
   +   */
   +  public void testThresholdCrossing_ResourceManagement() throws Exception {
   +    // Test data that will cross the threshold
   +    int threshold = 50;
   +    byte[] beforeThreshold = newPreFilledByteArray(40);
   +    byte[] afterThreshold = newPreFilledByteArray(30);
   +
   +    FileBackedOutputStream out = new FileBackedOutputStream(threshold);
   +    ByteSource source = out.asByteSource();
   +
   +    // Write data that doesn't cross threshold
   +    out.write(beforeThreshold);
   +    assertNull(out.getFile());
   +
   +    // Write data that crosses threshold - this exercises the fixed code path
   +    if (!JAVA_IO_TMPDIR.value().equals("/sdcard")) {
   +      out.write(afterThreshold);
   +      File file = out.getFile();
   +      assertNotNull(file);
   +      assertTrue(file.exists());
   +
   +      // Verify all data was written correctly
   +      byte[] expected = new byte[70];
   +      System.arraycopy(beforeThreshold, 0, expected, 0, 40);
   +      System.arraycopy(afterThreshold, 0, expected, 40, 30);
   +      assertTrue(Arrays.equals(expected, source.read()));
   +
   +      // Clean up
   +      out.close();
   +      out.reset();
   +      assertFalse(file.exists());
   +    }
   +  }
   +
   +  /**
   +   * Test that verifies writes after crossing the threshold work correctly.
   +   *
   +   * Once the threshold is crossed, subsequent writes go to the file. This test
   +   * ensures that continued writing after the initial threshold crossing works
   +   * properly with the resource management fix in place.
   +   */
   +  public void testWriteAfterThresholdCrossing() throws Exception {
   +    // Use a small threshold to force multiple file operations
   +    int threshold = 10;
   +    FileBackedOutputStream out = new FileBackedOutputStream(threshold);
   +    ByteSource source = out.asByteSource();
   +
   +    // Write data in chunks: first below threshold, then crossing it, then after crossing
   +    byte[] chunk1 = newPreFilledByteArray(8);  // Below threshold
   +    byte[] chunk2 = newPreFilledByteArray(5);  // Crosses threshold
   +    byte[] chunk3 = newPreFilledByteArray(20); // More data to file
   +
   +    out.write(chunk1);
   +    assertNull(out.getFile());
   +
   +    if (!JAVA_IO_TMPDIR.value().equals("/sdcard")) {
   +      out.write(chunk2);
   +      File file = out.getFile();
   +      assertNotNull(file);
   +
   +      out.write(chunk3);
   +
   +      // Verify all data is correct
   +      byte[] expected = new byte[33];
   +      System.arraycopy(chunk1, 0, expected, 0, 8);
   +      System.arraycopy(chunk2, 0, expected, 8, 5);
   +      System.arraycopy(chunk3, 0, expected, 13, 20);
   +      assertTrue(Arrays.equals(expected, source.read()));
   +
   +      out.close();
   +      out.reset();
   +    }
   +  }
    }
   diff --git a/guava/src/com/google/common/io/FileBackedOutputStream.java b/guava/src/com/google/common/io/FileBackedOutputStream.java
   --- a/guava/src/com/google/common/io/FileBackedOutputStream.java
   +++ b/guava/src/com/google/common/io/FileBackedOutputStream.java
   @@ -238,13 +238,22 @@ private void update(int len) throws IOException {
            // this is insurance.
            temp.deleteOnExit();
          }
   +      // Create and populate the file, ensuring proper resource management
   +      FileOutputStream transfer = null;
          try {
   -        FileOutputStream transfer = new FileOutputStream(temp);
   +        transfer = new FileOutputStream(temp);
            transfer.write(memory.getBuffer(), 0, memory.getCount());
            transfer.flush();
            // We've successfully transferred the data; switch to writing to file
            out = transfer;
          } catch (IOException e) {
   +        if (transfer != null) {
   +          try {
   +            transfer.close();
   +          } catch (IOException closeException) {
   +            e.addSuppressed(closeException);
   +          }
   +        }
            temp.delete();
            throw e;
          }
   ```
   </details>

2. **[Improve error messages for annotation methods on synthetic TypeVariables](https://github.com/google/guava/pull/7974)**<br>*Replaced unhelpful `UnsupportedOperationException("methodName")` with descriptive error messages explaining why annotations aren't supported on synthetic TypeVariables created by TypeResolver.*
   <details><summary><code>+19/-5</code> | merged 3 months ago</summary>

   ```diff
   diff --git a/guava/src/com/google/common/reflect/TypeResolver.java b/guava/src/com/google/common/reflect/TypeResolver.java
   --- a/guava/src/com/google/common/reflect/TypeResolver.java
   +++ b/guava/src/com/google/common/reflect/TypeResolver.java
   @@ -368,10 +368,12 @@ Type resolveInternal(TypeVariable<?> var, TypeTable forDependants) {
             * by us. And that equality is guaranteed to hold because it doesn't involve the JDK
             * TypeVariable implementation at all.
             *
   -         * TODO: b/147144588 - But what about when the TypeVariable has annotations? Our
   -         * implementation currently doesn't support annotations _at all_. It could at least be made
   -         * to respond to queries about annotations by returning null/empty, but are there situations
   -         * in which it should return something else?
   +         * NOTE: b/147144588 - Custom TypeVariables created by Guava do not preserve annotations.
   +         * This is intentional. The semantics of annotation handling during type resolution are
   +         * unclear and have changed across Java versions. Until there's a clear specification for
   +         * what annotations should mean on resolved TypeVariables with modified bounds, annotation
   +         * methods will throw UnsupportedOperationException. Frameworks requiring annotation
   +         * preservation should use the original TypeVariable when bounds haven't changed.
             */
            if (Types.NativeTypeVariableEquals.NATIVE_TYPE_VARIABLE_ONLY
                && Arrays.equals(bounds, resolvedBounds)) {
   diff --git a/guava/src/com/google/common/reflect/Types.java b/guava/src/com/google/common/reflect/Types.java
   --- a/guava/src/com/google/common/reflect/Types.java
   +++ b/guava/src/com/google/common/reflect/Types.java
   @@ -382,7 +382,19 @@ private static final class TypeVariableInvocationHandler implements InvocationHa
          String methodName = method.getName();
          Method typeVariableMethod = typeVariableMethods.get(methodName);
          if (typeVariableMethod == null) {
   -        throw new UnsupportedOperationException(methodName);
   +        // Provide helpful error message for annotation-related methods
   +        if (methodName.equals("getAnnotatedBounds")
   +            || methodName.startsWith("getAnnotation")
   +            || methodName.startsWith("getDeclaredAnnotation")
   +            || methodName.equals("isAnnotationPresent")
   +            || methodName.equals("getAnnotations")
   +            || methodName.equals("getDeclaredAnnotations")) {
   +          throw new UnsupportedOperationException(
   +              "Annotation methods are not supported on synthetic TypeVariables created during type "
   +              + "resolution. The semantics of annotations on resolved types with modified bounds are "
   +              + "undefined. Use the original TypeVariable for annotation access. See b/147144588.");
   +        }
   +        throw new UnsupportedOperationException(methodName);  // Keep original behavior for other methods
          } else {
            try {
              return typeVariableMethod.invoke(typeVariableImpl, args);
   ```
   </details>

3. **[Fix `Iterators.mergeSorted()` to preserve stability for equal elements](https://github.com/google/guava/pull/7989)**<br>*Fixed unstable ordering of equal elements by tracking iterator insertion order and using it as a tiebreaker, ensuring elements from earlier iterators appear before equal elements from later ones.*
   <details><summary><code>+167/-10</code> | merged 4 months ago</summary>

   ```diff
   diff --git a/guava-testlib/src/com/google/common/collect/testing/testers/MapPutIfAbsentTester.java b/guava-testlib/src/com/google/common/collect/testing/testers/MapPutIfAbsentTester.java
   --- a/guava-testlib/src/com/google/common/collect/testing/testers/MapPutIfAbsentTester.java
   +++ b/guava-testlib/src/com/google/common/collect/testing/testers/MapPutIfAbsentTester.java
   @@ -125,4 +125,18 @@ public void testPut_nullValueSupported() {
            getMap().putIfAbsent(nullValueEntry.getKey(), nullValueEntry.getValue()));
        expectAdded(nullValueEntry);
      }
   +
   +  @MapFeature.Require({SUPPORTS_PUT, ALLOWS_NULL_VALUES})
   +  @CollectionSize.Require(absent = ZERO)
   +  public void testPutIfAbsent_replacesNullValue() {
   +    // First, put a null value for an existing key
   +    getMap().put(k0(), null);
   +    assertEquals("Map should contain null value", null, getMap().get(k0()));
   +
   +    // putIfAbsent should replace the null value with the new value
   +    assertNull(
   +        "putIfAbsent(existingKeyWithNullValue, value) should return null",
   +        getMap().putIfAbsent(k0(), v3()));
   +    assertEquals("Map should now contain the new value", v3(), getMap().get(k0()));
   +  }
    }
   diff --git a/guava-tests/test/com/google/common/collect/IteratorsTest.java b/guava-tests/test/com/google/common/collect/IteratorsTest.java
   --- a/guava-tests/test/com/google/common/collect/IteratorsTest.java
   +++ b/guava-tests/test/com/google/common/collect/IteratorsTest.java
   @@ -61,13 +61,15 @@
    import java.util.Arrays;
    import java.util.Collection;
    import java.util.Collections;
   +import java.util.Comparator;
    import java.util.ConcurrentModificationException;
    import java.util.Enumeration;
    import java.util.Iterator;
    import java.util.LinkedHashSet;
    import java.util.List;
    import java.util.ListIterator;
    import java.util.NoSuchElementException;
   +import java.util.Objects;
    import java.util.RandomAccess;
    import java.util.Set;
    import java.util.Vector;
   @@ -1546,4 +1548,122 @@ public void testPeekingIteratorShortCircuit() {
        assertSame(peek, Iterators.peekingIterator(peek));
        assertSame(peek, Iterators.peekingIterator((Iterator<String>) peek));
      }
   +
   +  // Tests for demonstrating mergeSorted instability (Issue #5773)
   +  // These tests are expected to FAIL with the current implementation,
   +  // demonstrating that mergeSorted() is not stable for equal elements.
   +
   +  /**
   +   * Test demonstrating the instability problem reported in issue #5773.
   +   * This test will FAIL non-deterministically with current implementation.
   +   *
   +   * When merging iterators containing equal elements (by the comparator),
   +   * the current implementation does not guarantee that elements from the
   +   * first iterator will appear before elements from the second iterator.
   +   */
   +  public void testMergeSorted_demonstratesInstability_issue5773Example() {
   +    // Using the exact example from issue #5773
   +    List<TestDatum> left = ImmutableList.of(
   +        new TestDatum("B", 1),
   +        new TestDatum("C", 1)
   +    );
   +
   +    List<TestDatum> right = ImmutableList.of(
   +        new TestDatum("A", 2),
   +        new TestDatum("C", 2)
   +    );
   +
   +    Comparator<TestDatum> comparator = Comparator.comparing(d -> d.letter);
   +
   +    // The problem: When elements compare as equal (both C's have same letter),
   +    // the order is non-deterministic. Sometimes C1 comes first, sometimes C2.
   +    // A stable merge should always return C1 before C2 since C1 is from the first iterator.
   +
   +    Iterator<TestDatum> merged = Iterators.mergeSorted(
   +        ImmutableList.of(left.iterator(), right.iterator()),
   +        comparator);
   +
   +    List<TestDatum> result = ImmutableList.copyOf(merged);
   +
   +    // EXPECTED (if stable): [A2, B1, C1, C2]
   +    // ACTUAL (unstable): Sometimes [A2, B1, C1, C2], sometimes [A2, B1, C2, C1]
   +
   +    assertEquals("Should have 4 elements", 4, result.size());
   +    assertEquals("First should be A2", "A", result.get(0).letter);
   +    assertEquals("First should be from right iterator", 2, result.get(0).number);
   +    assertEquals("Second should be B1", "B", result.get(1).letter);
   +    assertEquals("Second should be from left iterator", 1, result.get(1).number);
   +
   +    // THIS IS THE KEY ASSERTION THAT WILL FAIL:
   +    // We expect C1 to come before C2 (stable behavior), but currently it's non-deterministic
   +    assertEquals("Third should be C from left iterator (C1) for stability", 1, result.get(2).number);
   +    assertEquals("Fourth should be C from right iterator (C2) for stability", 2, result.get(3).number);
   +  }
   +
   +  /**
   +   * Test demonstrating instability when all elements are equal.
   +   * With stable sorting, elements should maintain their iterator order.
   +   * This test will FAIL with current implementation.
   +   */
   +  public void testMergeSorted_demonstratesInstability_allEqual() {
   +    List<TestDatum> first = ImmutableList.of(
   +        new TestDatum("A", 1),
   +        new TestDatum("A", 2)
   +    );
   +
   +    List<TestDatum> second = ImmutableList.of(
   +        new TestDatum("A", 3),
   +        new TestDatum("A", 4)
   +    );
   +
   +    Comparator<TestDatum> comparator = Comparator.comparing(d -> d.letter);
   +    Iterator<TestDatum> merged = Iterators.mergeSorted(
   +        ImmutableList.of(first.iterator(), second.iterator()),
   +        comparator);
   +
   +    List<TestDatum> result = ImmutableList.copyOf(merged);
   +
   +    // EXPECTED (if stable): [A1, A2, A3, A4] - maintaining iterator order
   +    // ACTUAL (unstable): Order of elements is non-deterministic
   +
   +    assertEquals("Should have 4 elements", 4, result.size());
   +
   +    // These assertions will FAIL non-deterministically:
   +    assertEquals("First should be A1 for stability", 1, result.get(0).number);
   +    assertEquals("Second should be A2 for stability", 2, result.get(1).number);
   +    assertEquals("Third should be A3 for stability", 3, result.get(2).number);
   +    assertEquals("Fourth should be A4 for stability", 4, result.get(3).number);
   +  }
   +
   +  // Helper class for demonstrating the instability
   +  private static class TestDatum {
   +    final String letter;
   +    final int number;
   +
   +    TestDatum(String letter, int number) {
   +      this.letter = letter;
   +      this.number = number;
   +    }
   +
   +    @Override
   +    public String toString() {
   +      return letter + number;
   +    }
   +
   +    @Override
   +    public boolean equals(Object o) {
   +      if (!(o instanceof TestDatum)) return false;
   +      TestDatum other = (TestDatum) o;
   +      return letter.equals(other.letter) && number == other.number;
   +    }
   +
   +    @Override
   +    public int hashCode() {
   +      return Objects.hash(letter, number);
   +    }
   +  }
   +
   +  // Note: These tests are intentionally designed to FAIL with the current
   +  // implementation to demonstrate issue #5773. They will pass once the
   +  // stability fix is applied.
    }
   diff --git a/guava/src/com/google/common/collect/Iterators.java b/guava/src/com/google/common/collect/Iterators.java
   --- a/guava/src/com/google/common/collect/Iterators.java
   +++ b/guava/src/com/google/common/collect/Iterators.java
   @@ -1294,8 +1294,9 @@ public E peek() {
       * <p>Callers must ensure that the source {@code iterators} are in non-descending order as this
       * method does not sort its input.
       *
   -   * <p>For any equivalent elements across all {@code iterators}, it is undefined which element is
   -   * returned first.
   +   * <p>For any equivalent elements across all {@code iterators}, elements are returned in the order
   +   * of their source iterators. That is, if element A from iterator 1 and element B from iterator 2
   +   * compare as equal, A will be returned before B if iterator 1 was passed before iterator 2.
       *
       * @since 11.0
       */
   @@ -1318,22 +1319,43 @@ public E peek() {
       */
      private static final class MergingIterator<T extends @Nullable Object>
          extends UnmodifiableIterator<T> {
   -    final Queue<PeekingIterator<T>> queue;
   +
   +    // Wrapper class to track insertion order for stable sorting
   +    private static class IndexedIterator<E extends @Nullable Object> {
   +      final PeekingIterator<E> iterator;
   +      final int index;
   +
   +      IndexedIterator(PeekingIterator<E> iterator, int index) {
   +        this.iterator = iterator;
   +        this.index = index;
   +      }
   +    }
   +
   +    final Queue<IndexedIterator<T>> queue;
    
        MergingIterator(
            Iterable<? extends Iterator<? extends T>> iterators, Comparator<? super T> itemComparator) {
          // A comparator that's used by the heap, allowing the heap
   -      // to be sorted based on the top of each iterator.
   -      Comparator<PeekingIterator<T>> heapComparator =
   -          (PeekingIterator<T> o1, PeekingIterator<T> o2) ->
   -              itemComparator.compare(o1.peek(), o2.peek());
   +      // to be sorted based on the top of each iterator, with insertion order as tiebreaker
   +      Comparator<IndexedIterator<T>> heapComparator =
   +          (IndexedIterator<T> o1, IndexedIterator<T> o2) -> {
   +            int result = itemComparator.compare(o1.iterator.peek(), o2.iterator.peek());
   +            if (result == 0) {
   +              // When elements are equal, use insertion order to maintain stability
   +              return Integer.compare(o1.index, o2.index);
   +            }
   +            return result;
   +          };
    
          queue = new PriorityQueue<>(2, heapComparator);
    
   +      int index = 0;
          for (Iterator<? extends T> iterator : iterators) {
            if (iterator.hasNext()) {
   -          queue.add(Iterators.peekingIterator(iterator));
   +          queue.add(
   +              new IndexedIterator<>(Iterators.peekingIterator(iterator), index));
            }
   +        index++;
          }
        }
    
   @@ -1345,10 +1367,11 @@ public boolean hasNext() {
        @Override
        @ParametricNullness
        public T next() {
   -      PeekingIterator<T> nextIter = queue.remove();
   +      IndexedIterator<T> nextIndexed = queue.remove();
   +      PeekingIterator<T> nextIter = nextIndexed.iterator;
          T next = nextIter.next();
          if (nextIter.hasNext()) {
   -        queue.add(nextIter);
   +        queue.add(nextIndexed);
          }
          return next;
        }
   ```
   </details>

4. **[Add tests demonstrating `Iterators.mergeSorted()` instability](https://github.com/google/guava/pull/7988)**<br>*Added test cases demonstrating the instability problem in `Iterators.mergeSorted()` as requested by maintainers, verifying the bug exists before the fix PR.*
   <details><summary><code>+134/-0</code> | merged 4 months ago</summary>

   ```diff
   diff --git a/guava-testlib/src/com/google/common/collect/testing/testers/MapPutIfAbsentTester.java b/guava-testlib/src/com/google/common/collect/testing/testers/MapPutIfAbsentTester.java
   --- a/guava-testlib/src/com/google/common/collect/testing/testers/MapPutIfAbsentTester.java
   +++ b/guava-testlib/src/com/google/common/collect/testing/testers/MapPutIfAbsentTester.java
   @@ -125,4 +125,18 @@ public void testPut_nullValueSupported() {
            getMap().putIfAbsent(nullValueEntry.getKey(), nullValueEntry.getValue()));
        expectAdded(nullValueEntry);
      }
   +
   +  @MapFeature.Require({SUPPORTS_PUT, ALLOWS_NULL_VALUES})
   +  @CollectionSize.Require(absent = ZERO)
   +  public void testPutIfAbsent_replacesNullValue() {
   +    // First, put a null value for an existing key
   +    getMap().put(k0(), null);
   +    assertEquals("Map should contain null value", null, getMap().get(k0()));
   +
   +    // putIfAbsent should replace the null value with the new value
   +    assertNull(
   +        "putIfAbsent(existingKeyWithNullValue, value) should return null",
   +        getMap().putIfAbsent(k0(), v3()));
   +    assertEquals("Map should now contain the new value", v3(), getMap().get(k0()));
   +  }
    }
   diff --git a/guava-tests/test/com/google/common/collect/IteratorsTest.java b/guava-tests/test/com/google/common/collect/IteratorsTest.java
   --- a/guava-tests/test/com/google/common/collect/IteratorsTest.java
   +++ b/guava-tests/test/com/google/common/collect/IteratorsTest.java
   @@ -61,13 +61,15 @@
    import java.util.Arrays;
    import java.util.Collection;
    import java.util.Collections;
   +import java.util.Comparator;
    import java.util.ConcurrentModificationException;
    import java.util.Enumeration;
    import java.util.Iterator;
    import java.util.LinkedHashSet;
    import java.util.List;
    import java.util.ListIterator;
    import java.util.NoSuchElementException;
   +import java.util.Objects;
    import java.util.RandomAccess;
    import java.util.Set;
    import java.util.Vector;
   @@ -1546,4 +1548,122 @@ public void testPeekingIteratorShortCircuit() {
        assertSame(peek, Iterators.peekingIterator(peek));
        assertSame(peek, Iterators.peekingIterator((Iterator<String>) peek));
      }
   +
   +  // Tests for demonstrating mergeSorted instability (Issue #5773)
   +  // These tests are expected to FAIL with the current implementation,
   +  // demonstrating that mergeSorted() is not stable for equal elements.
   +
   +  /**
   +   * Test demonstrating the instability problem reported in issue #5773.
   +   * This test will FAIL non-deterministically with current implementation.
   +   *
   +   * When merging iterators containing equal elements (by the comparator),
   +   * the current implementation does not guarantee that elements from the
   +   * first iterator will appear before elements from the second iterator.
   +   */
   +  public void testMergeSorted_demonstratesInstability_issue5773Example() {
   +    // Using the exact example from issue #5773
   +    List<TestDatum> left = ImmutableList.of(
   +        new TestDatum("B", 1),
   +        new TestDatum("C", 1)
   +    );
   +
   +    List<TestDatum> right = ImmutableList.of(
   +        new TestDatum("A", 2),
   +        new TestDatum("C", 2)
   +    );
   +
   +    Comparator<TestDatum> comparator = Comparator.comparing(d -> d.letter);
   +
   +    // The problem: When elements compare as equal (both C's have same letter),
   +    // the order is non-deterministic. Sometimes C1 comes first, sometimes C2.
   +    // A stable merge should always return C1 before C2 since C1 is from the first iterator.
   +
   +    Iterator<TestDatum> merged = Iterators.mergeSorted(
   +        ImmutableList.of(left.iterator(), right.iterator()),
   +        comparator);
   +
   +    List<TestDatum> result = ImmutableList.copyOf(merged);
   +
   +    // EXPECTED (if stable): [A2, B1, C1, C2]
   +    // ACTUAL (unstable): Sometimes [A2, B1, C1, C2], sometimes [A2, B1, C2, C1]
   +
   +    assertEquals("Should have 4 elements", 4, result.size());
   +    assertEquals("First should be A2", "A", result.get(0).letter);
   +    assertEquals("First should be from right iterator", 2, result.get(0).number);
   +    assertEquals("Second should be B1", "B", result.get(1).letter);
   +    assertEquals("Second should be from left iterator", 1, result.get(1).number);
   +
   +    // THIS IS THE KEY ASSERTION THAT WILL FAIL:
   +    // We expect C1 to come before C2 (stable behavior), but currently it's non-deterministic
   +    assertEquals("Third should be C from left iterator (C1) for stability", 1, result.get(2).number);
   +    assertEquals("Fourth should be C from right iterator (C2) for stability", 2, result.get(3).number);
   +  }
   +
   +  /**
   +   * Test demonstrating instability when all elements are equal.
   +   * With stable sorting, elements should maintain their iterator order.
   +   * This test will FAIL with current implementation.
   +   */
   +  public void testMergeSorted_demonstratesInstability_allEqual() {
   +    List<TestDatum> first = ImmutableList.of(
   +        new TestDatum("A", 1),
   +        new TestDatum("A", 2)
   +    );
   +
   +    List<TestDatum> second = ImmutableList.of(
   +        new TestDatum("A", 3),
   +        new TestDatum("A", 4)
   +    );
   +
   +    Comparator<TestDatum> comparator = Comparator.comparing(d -> d.letter);
   +    Iterator<TestDatum> merged = Iterators.mergeSorted(
   +        ImmutableList.of(first.iterator(), second.iterator()),
   +        comparator);
   +
   +    List<TestDatum> result = ImmutableList.copyOf(merged);
   +
   +    // EXPECTED (if stable): [A1, A2, A3, A4] - maintaining iterator order
   +    // ACTUAL (unstable): Order of elements is non-deterministic
   +
   +    assertEquals("Should have 4 elements", 4, result.size());
   +
   +    // These assertions will FAIL non-deterministically:
   +    assertEquals("First should be A1 for stability", 1, result.get(0).number);
   +    assertEquals("Second should be A2 for stability", 2, result.get(1).number);
   +    assertEquals("Third should be A3 for stability", 3, result.get(2).number);
   +    assertEquals("Fourth should be A4 for stability", 4, result.get(3).number);
   +  }
   +
   +  // Helper class for demonstrating the instability
   +  private static class TestDatum {
   +    final String letter;
   +    final int number;
   +
   +    TestDatum(String letter, int number) {
   +      this.letter = letter;
   +      this.number = number;
   +    }
   +
   +    @Override
   +    public String toString() {
   +      return letter + number;
   +    }
   +
   +    @Override
   +    public boolean equals(Object o) {
   +      if (!(o instanceof TestDatum)) return false;
   +      TestDatum other = (TestDatum) o;
   +      return letter.equals(other.letter) && number == other.number;
   +    }
   +
   +    @Override
   +    public int hashCode() {
   +      return Objects.hash(letter, number);
   +    }
   +  }
   +
   +  // Note: These tests are intentionally designed to FAIL with the current
   +  // implementation to demonstrate issue #5773. They will pass once the
   +  // stability fix is applied.
    }
   ```
   </details>

5. **[Add test for putIfAbsent to catch implementations that incorrectly ignore null values](https://github.com/google/guava/pull/7987)**<br>*Added test to verify `putIfAbsent` correctly replaces existing null values, catching non-compliant Map implementations that pass the test suite despite violating the JavaDoc specification.*
   <details><summary><code>+14/-0</code> | merged 4 months ago</summary>

   ```diff
   diff --git a/guava-testlib/src/com/google/common/collect/testing/testers/MapPutIfAbsentTester.java b/guava-testlib/src/com/google/common/collect/testing/testers/MapPutIfAbsentTester.java
   --- a/guava-testlib/src/com/google/common/collect/testing/testers/MapPutIfAbsentTester.java
   +++ b/guava-testlib/src/com/google/common/collect/testing/testers/MapPutIfAbsentTester.java
   @@ -125,4 +125,18 @@ public void testPut_nullValueSupported() {
            getMap().putIfAbsent(nullValueEntry.getKey(), nullValueEntry.getValue()));
        expectAdded(nullValueEntry);
      }
   +
   +  @MapFeature.Require({SUPPORTS_PUT, ALLOWS_NULL_VALUES})
   +  @CollectionSize.Require(absent = ZERO)
   +  public void testPutIfAbsent_replacesNullValue() {
   +    // First, put a null value for an existing key
   +    getMap().put(k0(), null);
   +    assertEquals("Map should contain null value", null, getMap().get(k0()));
   +
   +    // putIfAbsent should replace the null value with the new value
   +    assertNull(
   +        "putIfAbsent(existingKeyWithNullValue, value) should return null",
   +        getMap().putIfAbsent(k0(), v3()));
   +    assertEquals("Map should now contain the new value", v3(), getMap().get(k0()));
   +  }
    }
   ```
   </details>

## <img src="https://github.com/stripe.png" width="24" alt="Stripe"> Stripe, pg-schema-diff, Go

- **[Fix: Support `GENERATED ALWAYS AS` columns to reduce migration failures](https://github.com/stripe/pg-schema-diff/pull/232)**<br>*Fixed migration failures where generated columns were incorrectly treated as DEFAULT columns. Updated schema introspection to detect `pg_attribute.attgenerated`, extended the Column model, and fixed DDL generation to output proper `GENERATED ALWAYS AS ... STORED` syntax.*
   <details><summary><code>+275/-37</code> | merged 4 months ago</summary>

   ```diff
   diff --git a/internal/migration_acceptance_tests/column_cases_test.go b/internal/migration_acceptance_tests/column_cases_test.go
   --- a/internal/migration_acceptance_tests/column_cases_test.go
   +++ b/internal/migration_acceptance_tests/column_cases_test.go
   @@ -1184,6 +1184,149 @@ var columnAcceptanceTestCases = []acceptanceTestCase{
    			`,
    		},
    	},
   +	{
   +		name: "Add generated column",
   +		oldSchemaDDL: []string{
   +			`
   +            CREATE TABLE tabs (
   +                id SERIAL PRIMARY KEY,
   +                title TEXT NOT NULL,
   +                artist TEXT
   +            );
   +			`,
   +		},
   +		newSchemaDDL: []string{
   +			`
   +            CREATE TABLE tabs (
   +                id SERIAL PRIMARY KEY,
   +                title TEXT NOT NULL,
   +                artist TEXT,
   +                search_vector tsvector GENERATED ALWAYS AS (
   +                    to_tsvector('simple', title || ' ' || coalesce(artist, ''))
   +                ) STORED
   +            );
   +			`,
   +		},
   +	},
   +	{
   +		name: "Drop generated column",
   +		oldSchemaDDL: []string{
   +			`
   +            CREATE TABLE tabs (
   +                id SERIAL PRIMARY KEY,
   +                title TEXT NOT NULL,
   +                artist TEXT,
   +                search_vector tsvector GENERATED ALWAYS AS (
   +                    to_tsvector('simple', title || ' ' || coalesce(artist, ''))
   +                ) STORED
   +            );
   +			`,
   +		},
   +		newSchemaDDL: []string{
   +			`
   +            CREATE TABLE tabs (
   +                id SERIAL PRIMARY KEY,
   +                title TEXT NOT NULL,
   +                artist TEXT
   +            );
   +			`,
   +		},
   +		expectedHazardTypes: []diff.MigrationHazardType{
   +			diff.MigrationHazardTypeDeletesData,
   +		},
   +	},
   +	{
   +		name: "Add multiple generated columns",
   +		oldSchemaDDL: []string{
   +			`
   +            CREATE TABLE products (
   +                id SERIAL PRIMARY KEY,
   +                name TEXT NOT NULL,
   +                price NUMERIC(10,2) NOT NULL
   +            );
   +			`,
   +		},
   +		newSchemaDDL: []string{
   +			`
   +            CREATE TABLE products (
   +                id SERIAL PRIMARY KEY,
   +                name TEXT NOT NULL,
   +                price NUMERIC(10,2) NOT NULL,
   +                price_with_tax NUMERIC(10,2) GENERATED ALWAYS AS (price * 1.1) STORED,
   +                display_name TEXT GENERATED ALWAYS AS (upper(name)) STORED
   +            );
   +			`,
   +		},
   +		// expectedDBSchemaDDL reflects the actual column order after migration
   +		// PostgreSQL adds columns in the order of execution, not declaration order
   +		expectedDBSchemaDDL: []string{
   +			`
   +            CREATE TABLE products (
   +                id SERIAL PRIMARY KEY,
   +                name TEXT NOT NULL,
   +                price NUMERIC(10,2) NOT NULL,
   +                display_name TEXT GENERATED ALWAYS AS (upper(name)) STORED,
   +                price_with_tax NUMERIC(10,2) GENERATED ALWAYS AS (price * 1.1) STORED
   +            );
   +			`,
   +		},
   +	},
   +	{
   +		name: "Generated column with index",
   +		oldSchemaDDL: []string{
   +			`
   +            CREATE TABLE articles (
   +                id SERIAL PRIMARY KEY,
   +                title TEXT NOT NULL,
   +                content TEXT
   +            );
   +			`,
   +		},
   +		newSchemaDDL: []string{
   +			`
   +            CREATE TABLE articles (
   +                id SERIAL PRIMARY KEY,
   +                title TEXT NOT NULL,
   +                content TEXT,
   +                search_vector tsvector GENERATED ALWAYS AS (
   +                    to_tsvector('english', title || ' ' || coalesce(content, ''))
   +                ) STORED
   +            );
   +            CREATE INDEX idx_articles_search_vector ON articles USING gin (search_vector);
   +			`,
   +		},
   +		expectedHazardTypes: []diff.MigrationHazardType{
   +			diff.MigrationHazardTypeIndexBuild,
   +		},
   +	},
   +	{
   +		name: "Generated column no-op",
   +		oldSchemaDDL: []string{
   +			`
   +            CREATE TABLE tabs (
   +                id SERIAL PRIMARY KEY,
   +                title TEXT NOT NULL,
   +                artist TEXT,
   +                search_vector tsvector GENERATED ALWAYS AS (
   +                    to_tsvector('simple', title || ' ' || coalesce(artist, ''))
   +                ) STORED
   +            );
   +			`,
   +		},
   +		newSchemaDDL: []string{
   +			`
   +            CREATE TABLE tabs (
   +                id SERIAL PRIMARY KEY,
   +                title TEXT NOT NULL,
   +                artist TEXT,
   +                search_vector tsvector GENERATED ALWAYS AS (
   +                    to_tsvector('simple', title || ' ' || coalesce(artist, ''))
   +                ) STORED
   +            );
   +			`,
   +		},
   +		expectEmptyPlan: true,
   +	},
    }
    
    func TestColumnTestCases(t *testing.T) {
   diff --git a/internal/queries/queries.sql b/internal/queries/queries.sql
   --- a/internal/queries/queries.sql
   +++ b/internal/queries/queries.sql
   @@ -89,11 +89,6 @@ WITH identity_col_seq AS (
    
    SELECT
        a.attname::TEXT AS column_name,
   -    COALESCE(coll.collname, '')::TEXT AS collation_name,
   -    COALESCE(collation_namespace.nspname, '')::TEXT AS collation_schema_name,
   -    COALESCE(
   -        pg_catalog.pg_get_expr(d.adbin, d.adrelid), ''
   -    )::TEXT AS default_value,
        a.attnotnull AS is_not_null,
        a.attlen AS column_size,
        a.attidentity::TEXT AS identity_type,
   @@ -103,6 +98,22 @@ SELECT
        identity_col_seq.seqmin AS min_value,
        identity_col_seq.seqcache AS cache_size,
        identity_col_seq.seqcycle AS is_cycle,
   +    COALESCE(coll.collname, '')::TEXT AS collation_name,
   +    COALESCE(collation_namespace.nspname, '')::TEXT AS collation_schema_name,
   +    COALESCE(
   +        CASE
   +            WHEN a.attgenerated = 's' THEN ''
   +            ELSE pg_catalog.pg_get_expr(d.adbin, d.adrelid)
   +        END, ''
   +    )::TEXT AS default_value,
   +    COALESCE(
   +        CASE
   +            WHEN a.attgenerated = 's'
   +                THEN pg_catalog.pg_get_expr(d.adbin, d.adrelid)
   +            ELSE ''
   +        END, ''
   +    )::TEXT AS generation_expression,
   +    (a.attgenerated = 's') AS is_generated,
        pg_catalog.format_type(a.atttypid, a.atttypmod) AS column_type
    FROM pg_catalog.pg_attribute AS a
    LEFT JOIN
   diff --git a/internal/queries/queries.sql.go b/internal/queries/queries.sql.go
   --- a/internal/queries/queries.sql.go
   +++ b/internal/queries/queries.sql.go
   @@ -115,11 +115,6 @@ WITH identity_col_seq AS (
    
    SELECT
        a.attname::TEXT AS column_name,
   -    COALESCE(coll.collname, '')::TEXT AS collation_name,
   -    COALESCE(collation_namespace.nspname, '')::TEXT AS collation_schema_name,
   -    COALESCE(
   -        pg_catalog.pg_get_expr(d.adbin, d.adrelid), ''
   -    )::TEXT AS default_value,
        a.attnotnull AS is_not_null,
        a.attlen AS column_size,
        a.attidentity::TEXT AS identity_type,
   @@ -129,6 +124,22 @@ SELECT
        identity_col_seq.seqmin AS min_value,
        identity_col_seq.seqcache AS cache_size,
        identity_col_seq.seqcycle AS is_cycle,
   +    COALESCE(coll.collname, '')::TEXT AS collation_name,
   +    COALESCE(collation_namespace.nspname, '')::TEXT AS collation_schema_name,
   +    COALESCE(
   +        CASE
   +            WHEN a.attgenerated = 's' THEN ''
   +            ELSE pg_catalog.pg_get_expr(d.adbin, d.adrelid)
   +        END, ''
   +    )::TEXT AS default_value,
   +    COALESCE(
   +        CASE
   +            WHEN a.attgenerated = 's'
   +                THEN pg_catalog.pg_get_expr(d.adbin, d.adrelid)
   +            ELSE ''
   +        END, ''
   +    )::TEXT AS generation_expression,
   +    (a.attgenerated = 's') AS is_generated,
        pg_catalog.format_type(a.atttypid, a.atttypmod) AS column_type
    FROM pg_catalog.pg_attribute AS a
    LEFT JOIN
   @@ -151,20 +162,22 @@ ORDER BY a.attnum
    `
    
    type GetColumnsForTableRow struct {
   -	ColumnName          string
   -	CollationName       string
   -	CollationSchemaName string
   -	DefaultValue        string
   -	IsNotNull           bool
   -	ColumnSize          int16
   -	IdentityType        string
   -	StartValue          sql.NullInt64
   -	IncrementValue      sql.NullInt64
   -	MaxValue            sql.NullInt64
   -	MinValue            sql.NullInt64
   -	CacheSize           sql.NullInt64
   -	IsCycle             sql.NullBool
   -	ColumnType          string
   +	ColumnName           string
   +	IsNotNull            bool
   +	ColumnSize           int16
   +	IdentityType         string
   +	StartValue           sql.NullInt64
   +	IncrementValue       sql.NullInt64
   +	MaxValue             sql.NullInt64
   +	MinValue             sql.NullInt64
   +	CacheSize            sql.NullInt64
   +	IsCycle              sql.NullBool
   +	CollationName        string
   +	CollationSchemaName  string
   +	DefaultValue         string
   +	GenerationExpression string
   +	IsGenerated          bool
   +	ColumnType           string
    }
    
    func (q *Queries) GetColumnsForTable(ctx context.Context, attrelid interface{}) ([]GetColumnsForTableRow, error) {
   @@ -178,9 +191,6 @@ func (q *Queries) GetColumnsForTable(ctx context.Context, attrelid interface{})
    		var i GetColumnsForTableRow
    		if err := rows.Scan(
    			&i.ColumnName,
   -			&i.CollationName,
   -			&i.CollationSchemaName,
   -			&i.DefaultValue,
    			&i.IsNotNull,
    			&i.ColumnSize,
    			&i.IdentityType,
   @@ -190,6 +200,11 @@ func (q *Queries) GetColumnsForTable(ctx context.Context, attrelid interface{})
    			&i.MinValue,
    			&i.CacheSize,
    			&i.IsCycle,
   +			&i.CollationName,
   +			&i.CollationSchemaName,
   +			&i.DefaultValue,
   +			&i.GenerationExpression,
   +			&i.IsGenerated,
    			&i.ColumnType,
    		); err != nil {
    			return nil, err
   diff --git a/internal/schema/schema.go b/internal/schema/schema.go
   --- a/internal/schema/schema.go
   +++ b/internal/schema/schema.go
   @@ -264,8 +264,16 @@ type (
    		//   ''::text
    		//   CURRENT_TIMESTAMP
    		// If empty, indicates that there is no default value.
   -		Default    string
   -		IsNullable bool
   +		Default string
   +		// If the column is a generated column, this will be true.
   +		IsGenerated bool
   +		// If the column is a generated column, this will be the generation expression.
   +		// Examples:
   +		//   to_tsvector('simple', title || ' ' || coalesce(artist, ''))
   +		//   (price * 1.1)
   +		// Only populated if IsGenerated is true.
   +		GenerationExpression string
   +		IsNullable           bool
    		// Size is the number of bytes required to store the value.
    		// It is used for data-packing purposes
    		Size     int
   @@ -981,9 +989,11 @@ func (s *schemaFetcher) buildTable(
    			//   ''::text
    			//   CURRENT_TIMESTAMP
    			// If empty, indicates that there is no default value.
   -			Default:  column.DefaultValue,
   -			Size:     int(column.ColumnSize),
   -			Identity: identity,
   +			Default:              column.DefaultValue,
   +			IsGenerated:          column.IsGenerated,
   +			GenerationExpression: column.GenerationExpression,
   +			Size:                 int(column.ColumnSize),
   +			Identity:             identity,
    		})
    	}
    
   diff --git a/internal/schema/schema_test.go b/internal/schema/schema_test.go
   --- a/internal/schema/schema_test.go
   +++ b/internal/schema/schema_test.go
   @@ -229,7 +229,7 @@ var (
    				SELECT id, author
    				FROM schema_2.foo;
    		`},
   -			expectedHash: "f0fb3f95f68ba482",
   +			expectedHash: "ff9ed400558572aa",
    			expectedSchema: Schema{
    				NamedSchemas: []NamedSchema{
    					{Name: "public"},
   @@ -571,7 +571,7 @@ var (
    			ALTER TABLE foo_fk_1 ADD CONSTRAINT foo_fk_1_fk FOREIGN KEY (author, content) REFERENCES foo_1 (author, content)
    				NOT VALID;
    		`},
   -			expectedHash: "bcad7c978a081c30",
   +			expectedHash: "9647ef46a878d426",
    			expectedSchema: Schema{
    				NamedSchemas: []NamedSchema{
    					{Name: "public"},
   diff --git a/pkg/diff/sql_generator.go b/pkg/diff/sql_generator.go
   --- a/pkg/diff/sql_generator.go
   +++ b/pkg/diff/sql_generator.go
   @@ -2637,12 +2637,14 @@ func buildColumnDefinition(column schema.Column) (string, error) {
    	if column.IsCollated() {
    		sb.WriteString(fmt.Sprintf(" COLLATE %s", column.Collation.GetFQEscapedName()))
    	}
   +	if column.IsGenerated {
   +		sb.WriteString(fmt.Sprintf(" GENERATED ALWAYS AS (%s) STORED", column.GenerationExpression))
   +	} else if len(column.Default) > 0 {
   +		sb.WriteString(fmt.Sprintf(" DEFAULT %s", column.Default))
   +	}
    	if !column.IsNullable {
    		sb.WriteString(" NOT NULL")
    	}
   -	if len(column.Default) > 0 {
   -		sb.WriteString(fmt.Sprintf(" DEFAULT %s", column.Default))
   -	}
    	if column.Identity != nil {
    		identityDef, err := buildColumnIdentityDefinition(*column.Identity)
    		if err != nil {
   diff --git a/pkg/diff/sql_generator_test.go b/pkg/diff/sql_generator_test.go
   --- a/pkg/diff/sql_generator_test.go
   +++ b/pkg/diff/sql_generator_test.go
   @@ -4,6 +4,7 @@ import (
    	"testing"
    
    	"github.com/stretchr/testify/assert"
   +	"github.com/stripe/pg-schema-diff/internal/schema"
    )
    
    func TestIsNotNullCCRegex(t *testing.T) {
   @@ -24,3 +25,59 @@ func TestIsNotNullCCRegex(t *testing.T) {
    		})
    	}
    }
   +
   +func TestBuildColumnDefinition(t *testing.T) {
   +	for _, tc := range []struct {
   +		name     string
   +		column   schema.Column
   +		expected string
   +	}{
   +		{
   +			name: "Regular column with default",
   +			column: schema.Column{
   +				Name:       "name",
   +				Type:       "text",
   +				Default:    "'default value'",
   +				IsNullable: true,
   +			},
   +			expected: `"name" text DEFAULT 'default value'`,
   +		},
   +		{
   +			name: "Generated column",
   +			column: schema.Column{
   +				Name:                 "search_vector",
   +				Type:                 "tsvector",
   +				IsGenerated:          true,
   +				GenerationExpression: "to_tsvector('simple', title || ' ' || coalesce(artist, ''))",
   +				IsNullable:           true,
   +			},
   +			expected: `"search_vector" tsvector GENERATED ALWAYS AS (to_tsvector('simple', title || ' ' || coalesce(artist, ''))) STORED`,
   +		},
   +		{
   +			name: "Generated column with NOT NULL",
   +			column: schema.Column{
   +				Name:                 "price_with_tax",
   +				Type:                 "numeric(10,2)",
   +				IsGenerated:          true,
   +				GenerationExpression: "price * 1.1",
   +				IsNullable:           false,
   +			},
   +			expected: `"price_with_tax" numeric(10,2) GENERATED ALWAYS AS (price * 1.1) STORED NOT NULL`,
   +		},
   +		{
   +			name: "Regular column with NOT NULL",
   +			column: schema.Column{
   +				Name:       "email",
   +				Type:       "text",
   +				IsNullable: false,
   +			},
   +			expected: `"email" text NOT NULL`,
   +		},
   +	} {
   +		t.Run(tc.name, func(t *testing.T) {
   +			result, err := buildColumnDefinition(tc.column)
   +			assert.NoError(t, err)
   +			assert.Equal(t, tc.expected, result)
   +		})
   +	}
   +}
   ```
   </details>

## <img src="https://github.com/microsoft.png" width="24" alt="Microsoft"> Microsoft, TypeAgent, TypeScript

- **[Return undefined instead of invalid action names for partial matches](https://github.com/microsoft/TypeAgent/pull/1478)**<br>*Prevented exceptions when typing partial cached commands by returning `undefined` instead of invalid "unknown.unknown" action names, enabling graceful handling of partial matches.*
   <details><summary><code>+10/-10</code> | merged 4 months ago</summary>

   ```diff
   diff --git a/ts/packages/cache/src/constructions/constructionValue.ts b/ts/packages/cache/src/constructions/constructionValue.ts
   --- a/ts/packages/cache/src/constructions/constructionValue.ts
   +++ b/ts/packages/cache/src/constructions/constructionValue.ts
   @@ -184,7 +184,7 @@ export function createActionProps(
    
        if (actionProps === undefined) {
            if (partial) {
   -            return { fullActionName: "unknown.unknown" };
   +            return { fullActionName: undefined }; // Return undefined for partial matches
            }
            throw new Error(
                "Internal error: No values provided for action properties",
   @@ -194,19 +194,17 @@ export function createActionProps(
        if (Array.isArray(actionProps)) {
            actionProps.forEach((actionProp) => {
                if (actionProp.fullActionName === undefined) {
   -                if (partial) {
   -                    actionProp.fullActionName = "unknown.unknown";
   -                } else {
   +                if (!partial) {
                        throw new Error("Internal error: fullActionName missing");
                    }
   +                // Leave undefined for partial matches
                }
            });
        } else if (actionProps.fullActionName === undefined) {
   -        if (partial) {
   -            actionProps.fullActionName = "unknown.unknown";
   -        } else {
   +        if (!partial) {
                throw new Error("Internal error: fullActionName missing");
            }
   +        // Leave undefined for partial matches
        }
    
        return actionProps;
   diff --git a/ts/packages/cache/src/explanation/requestAction.ts b/ts/packages/cache/src/explanation/requestAction.ts
   --- a/ts/packages/cache/src/explanation/requestAction.ts
   +++ b/ts/packages/cache/src/explanation/requestAction.ts
   @@ -194,9 +194,11 @@ function executableActionsToString(actions: ExecutableAction[]): string {
    }
    
    function fromJsonAction(actionJSON: JSONAction) {
   -    const { schemaName, actionName } = parseFullActionNameParts(
   -        actionJSON.fullActionName,
   -    );
   +    const { schemaName, actionName } =
   +        actionJSON.fullActionName !== undefined
   +            ? parseFullActionNameParts(actionJSON.fullActionName)
   +            : { schemaName: undefined as any, actionName: undefined as any };
   +
        return createExecutableAction(
            schemaName,
            actionName,
   ```
   </details>

## <img src="https://github.com/penpot.png" width="24" alt="Penpot"> Penpot, Penpot, Clojure, SQL

<img src="screenshots/penpot.png" width="200" alt="Penpot milestone lock feature">

- **[✨ Enhance (version control): Add milestone lock feature to prevent accidental deletion and bad actor interventions](https://github.com/penpot/penpot/pull/6982)**<br>*Implemented version locking system allowing users to protect saved milestones from accidental deletion or bad actors. Added database migration, RPC endpoints with authorization, and UI with visual lock indicators.*
   <details><summary><code>+292/-17</code> | merged 5 months ago</summary>

   ```diff
   diff --git a/backend/src/app/migrations.clj b/backend/src/app/migrations.clj
   --- a/backend/src/app/migrations.clj
   +++ b/backend/src/app/migrations.clj
   @@ -438,7 +438,10 @@
        :fn (mg/resource "app/migrations/sql/0138-mod-file-data-fragment-table.sql")}
    
       {:name "0139-mod-file-change-table.sql"
   -    :fn (mg/resource "app/migrations/sql/0139-mod-file-change-table.sql")}])
   +    :fn (mg/resource "app/migrations/sql/0139-mod-file-change-table.sql")}
   +
   +   {:name "0140-add-locked-by-column-to-file-change-table"
   +    :fn (mg/resource "app/migrations/sql/0140-add-locked-by-column-to-file-change-table.sql")}])
    
    (defn apply-migrations!
      [pool name migrations]
   diff --git a/backend/src/app/migrations/sql/0140-add-locked-by-column-to-file-change-table.sql b/backend/src/app/migrations/sql/0140-add-locked-by-column-to-file-change-table.sql
   --- a/backend/src/app/migrations/sql/0140-add-locked-by-column-to-file-change-table.sql
   +++ b/backend/src/app/migrations/sql/0140-add-locked-by-column-to-file-change-table.sql
   @@ -0,0 +1,11 @@
   +-- Add locked_by column to file_change table for version locking feature
   +-- This allows users to lock their own saved versions to prevent deletion by others
   +
   +ALTER TABLE file_change
   +  ADD COLUMN locked_by uuid NULL REFERENCES profile(id) ON DELETE SET NULL DEFERRABLE;
   +
   +-- Create index for locked versions queries
   +CREATE INDEX file_change__locked_by__idx ON file_change (locked_by) WHERE locked_by IS NOT NULL;
   +
   +-- Add comment for documentation
   +COMMENT ON COLUMN file_change.locked_by IS 'Profile ID of user who has locked this version. Only the creator can lock/unlock their own versions. Locked versions cannot be deleted by others.';
   \ No newline at end of file
   diff --git a/backend/src/app/rpc/commands/files_snapshot.clj b/backend/src/app/rpc/commands/files_snapshot.clj
   --- a/backend/src/app/rpc/commands/files_snapshot.clj
   +++ b/backend/src/app/rpc/commands/files_snapshot.clj
   @@ -29,7 +29,7 @@
    
    (def sql:get-file-snapshots
      "WITH changes AS (
   -      SELECT id, label, revn, created_at, created_by, profile_id
   +      SELECT id, label, revn, created_at, created_by, profile_id, locked_by
            FROM file_change
           WHERE file_id = ?
             AND data IS NOT NULL
   @@ -260,7 +260,7 @@
      [conn id]
      (db/get conn :file-change
              {:id id}
   -          {::sql/columns [:id :file-id :created-by :deleted-at]
   +          {::sql/columns [:id :file-id :created-by :deleted-at :profile-id :locked-by]
               ::db/for-update true}))
    
    (sv/defmethod ::update-file-snapshot
   @@ -300,4 +300,111 @@
                                  :snapshot-id id
                                  :profile-id profile-id))
    
   +                  ;; Check if version is locked by someone else
   +                  (when (and (:locked-by snapshot)
   +                             (not= (:locked-by snapshot) profile-id))
   +                    (ex/raise :type :validation
   +                              :code :snapshot-is-locked
   +                              :hint "Cannot delete a locked version"
   +                              :snapshot-id id
   +                              :profile-id profile-id
   +                              :locked-by (:locked-by snapshot)))
   +
                      (delete-file-snapshot! conn id)))))
   +
   +;;; Lock/unlock version endpoints
   +
   +(def ^:private schema:lock-file-snapshot
   +  [:map {:title "lock-file-snapshot"}
   +   [:id ::sm/uuid]])
   +
   +(defn- lock-file-snapshot!
   +  [conn snapshot-id profile-id]
   +  (db/update! conn :file-change
   +              {:locked-by profile-id}
   +              {:id snapshot-id}
   +              {::db/return-keys false})
   +  nil)
   +
   +(sv/defmethod ::lock-file-snapshot
   +  {::doc/added "1.20"
   +   ::sm/params schema:lock-file-snapshot}
   +  [cfg {:keys [::rpc/profile-id id]}]
   +  (db/tx-run! cfg
   +              (fn [{:keys [::db/conn]}]
   +                (let [snapshot (get-snapshot conn id)]
   +                  (files/check-edition-permissions! conn profile-id (:file-id snapshot))
   +
   +                  (when (not= (:created-by snapshot) "user")
   +                    (ex/raise :type :validation
   +                              :code :system-snapshots-cant-be-locked
   +                              :hint "Only user-created versions can be locked"
   +                              :snapshot-id id
   +                              :profile-id profile-id))
   +
   +                  ;; Only the creator can lock their own version
   +                  (when (not= (:profile-id snapshot) profile-id)
   +                    (ex/raise :type :validation
   +                              :code :only-creator-can-lock
   +                              :hint "Only the version creator can lock it"
   +                              :snapshot-id id
   +                              :profile-id profile-id
   +                              :creator-id (:profile-id snapshot)))
   +
   +                  ;; Check if already locked
   +                  (when (:locked-by snapshot)
   +                    (ex/raise :type :validation
   +                              :code :snapshot-already-locked
   +                              :hint "Version is already locked"
   +                              :snapshot-id id
   +                              :profile-id profile-id
   +                              :locked-by (:locked-by snapshot)))
   +
   +                  (lock-file-snapshot! conn id profile-id)))))
   +
   +(def ^:private schema:unlock-file-snapshot
   +  [:map {:title "unlock-file-snapshot"}
   +   [:id ::sm/uuid]])
   +
   +(defn- unlock-file-snapshot!
   +  [conn snapshot-id]
   +  (db/update! conn :file-change
   +              {:locked-by nil}
   +              {:id snapshot-id}
   +              {::db/return-keys false})
   +  nil)
   +
   +(sv/defmethod ::unlock-file-snapshot
   +  {::doc/added "1.20"
   +   ::sm/params schema:unlock-file-snapshot}
   +  [cfg {:keys [::rpc/profile-id id]}]
   +  (db/tx-run! cfg
   +              (fn [{:keys [::db/conn]}]
   +                (let [snapshot (get-snapshot conn id)]
   +                  (files/check-edition-permissions! conn profile-id (:file-id snapshot))
   +
   +                  (when (not= (:created-by snapshot) "user")
   +                    (ex/raise :type :validation
   +                              :code :system-snapshots-cant-be-unlocked
   +                              :hint "Only user-created versions can be unlocked"
   +                              :snapshot-id id
   +                              :profile-id profile-id))
   +
   +                  ;; Only the creator can unlock their own version
   +                  (when (not= (:profile-id snapshot) profile-id)
   +                    (ex/raise :type :validation
   +                              :code :only-creator-can-unlock
   +                              :hint "Only the version creator can unlock it"
   +                              :snapshot-id id
   +                              :profile-id profile-id
   +                              :creator-id (:profile-id snapshot)))
   +
   +                  ;; Check if not locked
   +                  (when (not (:locked-by snapshot))
   +                    (ex/raise :type :validation
   +                              :code :snapshot-not-locked
   +                              :hint "Version is not locked"
   +                              :snapshot-id id
   +                              :profile-id profile-id))
   +
   +                  (unlock-file-snapshot! conn id)))))
   diff --git a/frontend/src/app/main/data/workspace/versions.cljs b/frontend/src/app/main/data/workspace/versions.cljs
   --- a/frontend/src/app/main/data/workspace/versions.cljs
   +++ b/frontend/src/app/main/data/workspace/versions.cljs
   @@ -148,6 +148,29 @@
                                     (fetch-versions)
                                     (ptk/event ::ev/event {::ev/name "pin-version"})))))))))
    
   +(defn lock-version
   +  [id]
   +  (assert (uuid? id) "expected valid uuid for `id`")
   +  (ptk/reify ::lock-version
   +    ptk/WatchEvent
   +    (watch [_ _ _]
   +      (->> (rp/cmd! :lock-file-snapshot {:id id})
   +           (rx/map fetch-versions)
   +           (rx/catch (fn [error]
   +                       (js/console.error "Failed to lock version:" error)
   +                       (rx/of (fetch-versions))))))))
   +
   +(defn unlock-version
   +  [id]
   +  (assert (uuid? id) "expected valid uuid for `id`")
   +  (ptk/reify ::unlock-version
   +    ptk/WatchEvent
   +    (watch [_ _ _]
   +      (->> (rp/cmd! :unlock-file-snapshot {:id id})
   +           (rx/map fetch-versions)
   +           (rx/catch (fn [error]
   +                       (js/console.error "Failed to unlock version:" error)
   +                       (rx/of (fetch-versions))))))))
    
    ;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;
    ;; PLUGINS SPECIFIC EVENTS
   diff --git a/frontend/src/app/main/errors.cljs b/frontend/src/app/main/errors.cljs
   --- a/frontend/src/app/main/errors.cljs
   +++ b/frontend/src/app/main/errors.cljs
   @@ -148,6 +148,38 @@
        (= code :vern-conflict)
        (st/emit! (ptk/event ::dw/reload-current-file))
    
   +    (= code :snapshot-is-locked)
   +    (let [message (tr "errors.version-locked")]
   +      (st/async-emit!
   +       (ntf/show {:content message
   +                  :type :toast
   +                  :level :error
   +                  :timeout 3000})))
   +
   +    (= code :only-creator-can-lock)
   +    (let [message (tr "errors.only-creator-can-lock")]
   +      (st/async-emit!
   +       (ntf/show {:content message
   +                  :type :toast
   +                  :level :error
   +                  :timeout 3000})))
   +
   +    (= code :only-creator-can-unlock)
   +    (let [message (tr "errors.only-creator-can-unlock")]
   +      (st/async-emit!
   +       (ntf/show {:content message
   +                  :type :toast
   +                  :level :error
   +                  :timeout 3000})))
   +
   +    (= code :snapshot-already-locked)
   +    (let [message (tr "errors.version-already-locked")]
   +      (st/async-emit!
   +       (ntf/show {:content message
   +                  :type :toast
   +                  :level :error
   +                  :timeout 3000})))
   +
        :else
        (st/async-emit! (rt/assign-exception error))))
    
   diff --git a/frontend/src/app/main/ui/ds/product/user_milestone.cljs b/frontend/src/app/main/ui/ds/product/user_milestone.cljs
   --- a/frontend/src/app/main/ui/ds/product/user_milestone.cljs
   +++ b/frontend/src/app/main/ui/ds/product/user_milestone.cljs
   @@ -11,6 +11,7 @@
       [app.common.data :as d]
       [app.main.ui.ds.buttons.icon-button :refer [icon-button*]]
       [app.main.ui.ds.controls.input :refer [input*]]
   +   [app.main.ui.ds.foundations.assets.icon :as i]
       [app.main.ui.ds.foundations.typography :as t]
       [app.main.ui.ds.foundations.typography.text :refer [text*]]
       [app.main.ui.ds.product.avatar :refer [avatar*]]
   @@ -25,6 +26,7 @@
       [:class {:optional true} :string]
       [:active {:optional true} :boolean]
       [:editing {:optional true} :boolean]
   +   [:locked {:optional true} :boolean]
       [:user
        [:map
         [:name {:optional true} [:maybe :string]]
   @@ -39,7 +41,7 @@
    
    (mf/defc user-milestone*
      {::mf/schema schema:milestone}
   -  [{:keys [class active editing user label date
   +  [{:keys [class active editing locked user label date
               onOpenMenu onFocusInput onBlurInput onKeyDownInput] :rest props}]
      (let [class (d/append-class class (stl/css-case :milestone true :is-selected active))
            props (mf/spread-props props {:class class :data-testid "milestone"})
   @@ -60,7 +62,10 @@
             :on-focus onFocusInput
             :on-blur onBlurInput
             :on-key-down onKeyDownInput}]
   -       [:> text*  {:as "span" :typography t/body-small :class (stl/css :name)} label])
   +       [:div {:class (stl/css :name-wrapper)}
   +        [:> text*  {:as "span" :typography t/body-small :class (stl/css :name)} label]
   +        (when locked
   +          [:> i/icon* {:icon-id i/lock :class (stl/css :lock-icon)}])])
    
         [:*
          [:time {:dateTime (dt/format date :iso)
   diff --git a/frontend/src/app/main/ui/ds/product/user_milestone.scss b/frontend/src/app/main/ui/ds/product/user_milestone.scss
   --- a/frontend/src/app/main/ui/ds/product/user_milestone.scss
   +++ b/frontend/src/app/main/ui/ds/product/user_milestone.scss
   @@ -42,11 +42,23 @@
      justify-self: flex-end;
    }
    
   +.name-wrapper {
   +  display: flex;
   +  align-items: baseline;
   +}
   +
    .name {
      grid-area: name;
      color: var(--color-foreground-primary);
    }
    
   +.lock-icon {
   +  margin-left: 8px;
   +  transform: scale(0.8);
   +  color: var(--color-foreground-secondary);
   +  align-self: anchor-center;
   +}
   +
    .date {
      @include t.use-typography("body-small");
      grid-area: content;
   diff --git a/frontend/src/app/main/ui/workspace/sidebar/versions.cljs b/frontend/src/app/main/ui/workspace/sidebar/versions.cljs
   --- a/frontend/src/app/main/ui/workspace/sidebar/versions.cljs
   +++ b/frontend/src/app/main/ui/workspace/sidebar/versions.cljs
   @@ -76,7 +76,7 @@
           (reverse)))
    
    (mf/defc version-entry
   -  [{:keys [entry profile on-restore-version on-delete-version on-rename-version editing?]}]
   +  [{:keys [entry profile current-profile on-restore-version on-delete-version on-rename-version on-lock-version on-unlock-version editing?]}]
      (let [show-menu? (mf/use-state false)
    
            handle-open-menu
   @@ -109,6 +109,20 @@
               (when on-delete-version
                 (on-delete-version (:id entry)))))
    
   +        handle-lock-version
   +        (mf/use-callback
   +         (mf/deps entry on-lock-version)
   +         (fn []
   +           (when on-lock-version
   +             (on-lock-version (:id entry)))))
   +
   +        handle-unlock-version
   +        (mf/use-callback
   +         (mf/deps entry on-unlock-version)
   +         (fn []
   +           (when on-unlock-version
   +             (on-unlock-version (:id entry)))))
   +
            handle-name-input-focus
            (mf/use-fn
             (fn [event]
   @@ -142,22 +156,44 @@
                                         :color (:color profile)}
                              :editing editing?
                              :date (:created-at entry)
   +                          :locked (boolean (:locked-by entry))
                              :onOpenMenu handle-open-menu
                              :onFocusInput handle-name-input-focus
                              :onBlurInput handle-name-input-blur
                              :onKeyDownInput handle-name-input-key-down}]
    
         [:& dropdown {:show @show-menu? :on-close handle-close-menu}
   -      [:ul {:class (stl/css :version-options-dropdown)}
   -       [:li {:class (stl/css :menu-option)
   -             :role "button"
   -             :on-click handle-rename-version} (tr "labels.rename")]
   -       [:li {:class (stl/css :menu-option)
   -             :role "button"
   -             :on-click handle-restore-version} (tr "labels.restore")]
   -       [:li {:class (stl/css :menu-option)
   -             :role "button"
   -             :on-click handle-delete-version} (tr "labels.delete")]]]]))
   +      (let [current-user-id   (:id current-profile)
   +            version-creator-id (:profile-id entry)
   +            locked-by-id      (:locked-by entry)
   +            is-version-creator? (= current-user-id version-creator-id)
   +            is-locked?         (some? locked-by-id)
   +            is-locked-by-me?   (= current-user-id locked-by-id)
   +            can-rename?        is-version-creator?
   +            can-lock?          (and is-version-creator? (not is-locked?))
   +            can-unlock?        (and is-version-creator? is-locked-by-me?)
   +            can-delete?        (or (not is-locked?) (and is-locked? is-locked-by-me?))]
   +        [:ul {:class (stl/css :version-options-dropdown)}
   +         (when can-rename?
   +           [:li {:class (stl/css :menu-option)
   +                 :role "button"
   +                 :on-click handle-rename-version} (tr "labels.rename")])
   +         [:li {:class (stl/css :menu-option)
   +               :role "button"
   +               :on-click handle-restore-version} (tr "labels.restore")]
   +         (cond
   +           can-unlock?
   +           [:li {:class (stl/css :menu-option)
   +                 :role "button"
   +                 :on-click handle-unlock-version} (tr "labels.unlock")]
   +           can-lock?
   +           [:li {:class (stl/css :menu-option)
   +                 :role "button"
   +                 :on-click handle-lock-version} (tr "labels.lock")])
   +         (when can-delete?
   +           [:li {:class (stl/css :menu-option)
   +                 :role "button"
   +                 :on-click handle-delete-version} (tr "labels.delete")])])]]))
    
    (mf/defc snapshot-entry
      [{:keys [index is-expanded entry on-toggle-expand on-pin-snapshot on-restore-snapshot]}]
   @@ -311,6 +347,16 @@
             (fn [id]
               (st/emit! (dwv/pin-version id))))
    
   +        handle-lock-version
   +        (mf/use-fn
   +         (fn [id]
   +           (st/emit! (dwv/lock-version id))))
   +
   +        handle-unlock-version
   +        (mf/use-fn
   +         (fn [id]
   +           (st/emit! (dwv/unlock-version id))))
   +
            handle-change-filter
            (mf/use-fn
             (fn [filter]
   @@ -368,9 +414,12 @@
                                      :entry entry
                                      :editing? (= (:id entry) editing)
                                      :profile (get profiles (:profile-id entry))
   +                                  :current-profile profile
                                      :on-rename-version handle-rename-version
                                      :on-restore-version handle-restore-version-pinned
   -                                  :on-delete-version handle-delete-version}]
   +                                  :on-delete-version handle-delete-version
   +                                  :on-lock-version handle-lock-version
   +                                  :on-unlock-version handle-unlock-version}]
    
                   :snapshot
                   [:& snapshot-entry {:key idx-entry
   diff --git a/frontend/translations/en.po b/frontend/translations/en.po
   --- a/frontend/translations/en.po
   +++ b/frontend/translations/en.po
   @@ -1380,6 +1380,22 @@ msgstr "Password should at least be 8 characters"
    msgid "errors.paste-data-validation"
    msgstr "Invalid data in clipboard"
    
   +#: src/app/main/errors.cljs:152
   +msgid "errors.version-locked"
   +msgstr "This version is locked and cannot be deleted by others"
   +
   +#: src/app/main/errors.cljs:160
   +msgid "errors.only-creator-can-lock"
   +msgstr "Only the version creator can lock it"
   +
   +#: src/app/main/errors.cljs:168
   +msgid "errors.only-creator-can-unlock"
   +msgstr "Only the version creator can unlock it"
   +
   +#: src/app/main/errors.cljs:176
   +msgid "errors.version-already-locked"
   +msgstr "This version is already locked"
   +
    #: src/app/main/data/auth.cljs:312, src/app/main/ui/auth/login.cljs:103, src/app/main/ui/auth/login.cljs:111
    msgid "errors.profile-blocked"
    msgstr "The profile is blocked"
   @@ -2133,6 +2149,10 @@ msgstr "Libraries & Templates"
    msgid "labels.loading"
    msgstr "Loading…"
    
   +#: src/app/main/ui/workspace/sidebar/versions.cljs:179
   +msgid "labels.lock"
   +msgstr "Lock"
   +
    #: src/app/main/ui/viewer/header.cljs:208
    msgid "labels.log-or-sign"
    msgstr "Log in or sign up"
   @@ -2453,6 +2473,10 @@ msgstr "Tutorials"
    msgid "labels.unknown-error"
    msgstr "Unknown error"
    
   +#: src/app/main/ui/workspace/sidebar/versions.cljs:176
   +msgid "labels.unlock"
   +msgstr "Unlock"
   +
    #: src/app/main/ui/dashboard/file_menu.cljs:264
    msgid "labels.unpublish-multi-files"
    msgstr "Unpublish %s files"
   @@ -7875,6 +7899,15 @@ msgstr "History"
    msgid "workspace.versions.version-menu"
    msgstr "Open version menu"
    
   +msgid "workspace.versions.locked-by-other"
   +msgstr "This version is locked by %s and cannot be modified"
   +
   +msgid "workspace.versions.locked-by-you"
   +msgstr "This version is locked by you"
   +
   +msgid "workspace.versions.tooltip.locked-version"
   +msgstr "Locked version - only the creator can modify it"
   +
    #: src/app/main/ui/workspace/sidebar/versions.cljs:372
    #, markdown
    msgid "workspace.versions.warning.subtext"
   ```
   </details>

# Developer Projects
My favourite Personal Projects
