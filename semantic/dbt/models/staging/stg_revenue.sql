-- Staging model for revenue transactions.
-- Extracted from the source OLTP database.
-- Replace with actual source table references.

WITH source AS (
    SELECT * FROM {{ source('raw', 'transactions') }}
),

renamed AS (
    SELECT
        id AS transaction_id,
        customer_id,
        amount AS revenue_amount,
        region,
        product_category,
        DATE(created_at) AS transaction_date,
        created_at,
        tenant_id
    FROM source
)

SELECT * FROM renamed
