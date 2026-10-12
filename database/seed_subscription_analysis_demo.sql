USE Subscription_Analysis;
GO

IF NOT EXISTS (SELECT 1 FROM dbo.Society_Master_Data WHERE SocietyID = 101)
BEGIN
    INSERT INTO dbo.Society_Master_Data
        (SocietyID, SocietyName, City, State, TotalFlats, OnboardingDate)
    VALUES
        (101, N'Green Heights Residency', N'Pune', N'Maharashtra', 240, '2025-01-15'),
        (102, N'Silver Oak Enclave', N'Mumbai', N'Maharashtra', 420, '2025-03-10'),
        (103, N'Lakeview Towers', N'Bengaluru', N'Karnataka', 360, '2025-05-22'),
        (104, N'Sunrise Habitat', N'Ahmedabad', N'Gujarat', 180, '2025-07-01'),
        (105, N'Palm Grove Society', N'Hyderabad', N'Telangana', 300, '2025-09-18');
END;
GO

IF NOT EXISTS (SELECT 1 FROM dbo.Subscription_Plans WHERE PlanID = 1)
BEGIN
    INSERT INTO dbo.Subscription_Plans
        (PlanID, PlanName, DurationMonths, Price, Features)
    VALUES
        (1, N'Basic', 12, 24000.00, N'Helpdesk, resident directory, notices'),
        (2, N'Professional', 12, 54000.00, N'Payments, helpdesk, accounting exports, reports'),
        (3, N'Enterprise', 12, 96000.00, N'Advanced analytics, priority support, integrations, audit logs');
END;
GO

IF NOT EXISTS (SELECT 1 FROM dbo.Subscription_Transactions WHERE SubscriptionID = 5001)
BEGIN
    INSERT INTO dbo.Subscription_Transactions
        (SubscriptionID, SocietyID, PlanID, StartDate, EndDate, Status)
    VALUES
        (5001, 101, 2, '2026-01-01', '2026-12-31', N'Active'),
        (5002, 102, 3, '2026-02-01', '2027-01-31', N'Active'),
        (5003, 103, 2, '2025-08-15', '2026-08-14', N'Active'),
        (5004, 104, 1, '2025-06-01', '2026-05-31', N'Expired'),
        (5005, 105, 3, '2025-09-01', '2026-08-20', N'Active');
END;
GO

IF NOT EXISTS (SELECT 1 FROM dbo.Payment_Gateway WHERE PaymentID = 9001)
BEGIN
    INSERT INTO dbo.Payment_Gateway
        (PaymentID, SocietyID, Amount, PaymentMethod, Status, PaymentDate)
    VALUES
        (9001, 101, 54000.00, N'UPI', N'Success', '2026-01-02'),
        (9002, 102, 96000.00, N'Bank Transfer', N'Success', '2026-02-02'),
        (9003, 103, 54000.00, N'Credit Card', N'Pending', '2026-07-28'),
        (9004, 104, 24000.00, N'UPI', N'Failed', '2026-06-01'),
        (9005, 105, 96000.00, N'Bank Transfer', N'Success', '2025-09-02');
END;
GO

IF NOT EXISTS (SELECT 1 FROM dbo.Complaint_tickets WHERE TicketID = 7001)
BEGIN
    INSERT INTO dbo.Complaint_tickets
        (TicketID, SocietyID, Category, CreatedDate, ResolvedDate, SLA_Hours, Status)
    VALUES
        (7001, 101, N'Payment', '2026-07-20T09:00:00', '2026-07-20T17:00:00', 12, N'Resolved'),
        (7002, 102, N'Login', '2026-07-22T10:30:00', '2026-07-23T15:00:00', 24, N'Resolved'),
        (7003, 103, N'Accounting Export', '2026-07-25T11:00:00', NULL, 48, N'Open'),
        (7004, 104, N'Renewal', '2026-07-10T14:00:00', '2026-07-13T16:00:00', 24, N'Resolved'),
        (7005, 105, N'Integration', '2026-07-26T08:45:00', NULL, 72, N'Open');
END;
GO

SELECT TOP 20 * FROM dbo.Society_Master_Data ORDER BY SocietyID;
SELECT TOP 20 * FROM dbo.Subscription_Plans ORDER BY PlanID;
SELECT TOP 20 * FROM dbo.Subscription_Transactions ORDER BY SubscriptionID;
SELECT TOP 20 * FROM dbo.Payment_Gateway ORDER BY PaymentID;
SELECT TOP 20 * FROM dbo.Complaint_tickets ORDER BY TicketID;
GO

