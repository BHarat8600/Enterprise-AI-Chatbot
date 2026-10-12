# Subscription Analysis Knowledge Base

## Business Definitions

- Active subscription: a row in `Subscription_Transactions` where `Status = 'Active'`.
- Renewal risk: a subscription that has expired, is not active, or ends in the next 30 days.
- Contract value: the plan `Price` attached to each active subscription transaction.
- Payment leakage: payment records where `Status` is not `Success`.
- SLA breach: a complaint ticket where actual hours from `CreatedDate` to `ResolvedDate` is greater than `SLA_Hours`. For open tickets, compare `CreatedDate` to the current time.

## Table Usage

- Use `Society_Master_Data` for society name, location, total flats, and onboarding date.
- Use `Subscription_Plans` for plan name, duration, price, and features.
- Use `Subscription_Transactions` for subscription lifecycle status, start date, and end date.
- Use `Payment_Gateway` for payment status, payment method, payment date, and amount.
- Use `Complaint_tickets` for operational health, complaint categories, and SLA performance.

## Recommended Analysis

- Compare subscription value by plan to understand monetization.
- Compare complaint SLA breaches by society to identify operational risk.
- Compare failed payments with expiring subscriptions to find renewal risk.
- Segment societies by city, state, and total flats before recommending plan upgrades.

