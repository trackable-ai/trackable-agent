-- Migration 006: Extend unique constraint to include order status
-- Enables order history preservation: each status transition creates
-- a new row instead of overwriting the existing one.
--
-- Old constraint: (user_id, merchant_id, order_number)
-- New constraint: (user_id, merchant_id, order_number, status)

-- Step 1: Drop existing unique constraint
ALTER TABLE orders
DROP CONSTRAINT IF EXISTS orders_user_merchant_order_number_unique;

-- Step 2: Remove duplicate rows (keep the most recently updated row per unique key)
DELETE FROM orders
WHERE id IN (
    SELECT id FROM (
        SELECT id,
               ROW_NUMBER() OVER (
                   PARTITION BY user_id, merchant_id, order_number, status
                   ORDER BY updated_at DESC
               ) AS rn
        FROM orders
    ) ranked
    WHERE rn > 1
);

-- Step 3: Add new unique constraint including status
ALTER TABLE orders
ADD CONSTRAINT orders_user_merchant_order_number_status_unique
UNIQUE (user_id, merchant_id, order_number, status);

-- Step 4: Add index for efficient "latest status" queries
CREATE INDEX IF NOT EXISTS idx_orders_latest_status
ON orders (user_id, merchant_id, order_number, created_at DESC);
