-- Migration 005: Add NOT NULL and unique constraint on orders.order_number
-- This ensures:
-- 1. All orders must have an order number
-- 2. No duplicate orders exist for the same user, merchant, and order number combination

-- Step 1: Delete orders without order_number (they are incomplete/invalid)
DELETE FROM orders WHERE order_number IS NULL;

-- Step 2: Add NOT NULL constraint on order_number
ALTER TABLE orders
ALTER COLUMN order_number SET NOT NULL;

-- Step 3: Add unique constraint (also creates an index for faster lookups)
ALTER TABLE orders
ADD CONSTRAINT orders_user_merchant_order_number_unique
UNIQUE (user_id, merchant_id, order_number);

-- To find any existing duplicates before migration:
-- SELECT user_id, merchant_id, order_number, COUNT(*)
-- FROM orders
-- GROUP BY user_id, merchant_id, order_number
-- HAVING COUNT(*) > 1;
