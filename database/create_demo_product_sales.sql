IF DB_ID(N'EnterpriseChatbotDemo') IS NULL
BEGIN
    CREATE DATABASE EnterpriseChatbotDemo;
END;
GO

USE EnterpriseChatbotDemo;
GO

IF OBJECT_ID(N'dbo.ProductSales', N'U') IS NOT NULL
BEGIN
    DROP TABLE dbo.ProductSales;
END;
GO

CREATE TABLE dbo.ProductSales
(
    SaleId INT NOT NULL PRIMARY KEY,
    SaleDate DATE NOT NULL,
    ProductName NVARCHAR(120) NOT NULL,
    Category NVARCHAR(80) NOT NULL,
    Region NVARCHAR(60) NOT NULL,
    CustomerSegment NVARCHAR(80) NOT NULL,
    Quantity INT NOT NULL,
    UnitPrice DECIMAL(12, 2) NOT NULL,
    DiscountPercent DECIMAL(5, 2) NOT NULL,
    SalesRep NVARCHAR(120) NOT NULL,
    NetRevenue AS CAST(Quantity * UnitPrice * (1 - DiscountPercent / 100.0) AS DECIMAL(14, 2)) PERSISTED
);
GO

INSERT INTO dbo.ProductSales
    (SaleId, SaleDate, ProductName, Category, Region, CustomerSegment, Quantity, UnitPrice, DiscountPercent, SalesRep)
VALUES
    (1001, '2026-07-01', N'Alpha Laptop', N'Computers', N'North', N'Enterprise', 6, 980.00, 5.0, N'Aarav Sharma'),
    (1002, '2026-07-02', N'Vertex Docking Station', N'Accessories', N'West', N'SMB', 18, 145.00, 2.5, N'Meera Iyer'),
    (1003, '2026-07-03', N'Nimbus Monitor 27', N'Displays', N'South', N'Enterprise', 12, 310.00, 4.0, N'Rohan Mehta'),
    (1004, '2026-07-04', N'SecureKey Pro', N'Security', N'East', N'Government', 40, 42.00, 0.0, N'Neha Rao'),
    (1005, '2026-07-05', N'Alpha Laptop', N'Computers', N'West', N'Enterprise', 4, 980.00, 7.5, N'Meera Iyer'),
    (1006, '2026-07-06', N'CloudDesk License', N'Software', N'North', N'SMB', 75, 19.00, 10.0, N'Aarav Sharma'),
    (1007, '2026-07-07', N'Nimbus Monitor 27', N'Displays', N'West', N'Enterprise', 8, 310.00, 3.0, N'Meera Iyer'),
    (1008, '2026-07-08', N'DataVault Backup', N'Software', N'South', N'Enterprise', 35, 49.00, 5.0, N'Rohan Mehta'),
    (1009, '2026-07-09', N'Vertex Docking Station', N'Accessories', N'East', N'SMB', 22, 145.00, 2.0, N'Neha Rao'),
    (1010, '2026-07-10', N'SecureKey Pro', N'Security', N'North', N'Government', 55, 42.00, 1.0, N'Aarav Sharma'),
    (1011, '2026-07-11', N'CloudDesk License', N'Software', N'West', N'Enterprise', 120, 19.00, 12.0, N'Meera Iyer'),
    (1012, '2026-07-12', N'DataVault Backup', N'Software', N'East', N'Government', 50, 49.00, 6.0, N'Neha Rao');
GO

SELECT TOP 20 * FROM dbo.ProductSales ORDER BY SaleDate DESC;
GO

