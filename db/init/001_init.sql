-- ============================================================
--  VAT_REFUNDER schema initialization
-- ============================================================

CREATE DATABASE IF NOT EXISTS invoice_processing_pipeline CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
USE vat_refunder;

-- ============================================================
-- 1. Head_of_Accounts
-- ============================================================
CREATE TABLE IF NOT EXISTS Head_of_Accounts (
  Head_of_Accounts_ID INT NOT NULL AUTO_INCREMENT,
  Name VARCHAR(255) NOT NULL,
  PRIMARY KEY (Head_of_Accounts_ID)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ============================================================
-- 2. NIF_Codes
-- ============================================================
CREATE TABLE IF NOT EXISTS NIF_Codes (
  Supplier_ID INT NOT NULL AUTO_INCREMENT,
  Supplier_NIF_Code VARCHAR(255) DEFAULT NULL,
  Supplier_Name VARCHAR(255) NOT NULL,
  PRIMARY KEY (Supplier_ID),
  UNIQUE KEY Supplier_Name (Supplier_Name),
  UNIQUE KEY Supplier_NIF_Code (Supplier_NIF_Code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ============================================================
-- 3. Vouchers
-- ============================================================
CREATE TABLE IF NOT EXISTS Vouchers (
  Voucher_ID INT NOT NULL AUTO_INCREMENT,
  Voucher_Number VARCHAR(255) DEFAULT NULL,
  Head_of_Accounts_ID INT DEFAULT NULL,
  Voucher_Beneficiary VARCHAR(225) DEFAULT NULL,
  Voucher_Euro DECIMAL(10,2) DEFAULT NULL,
  Voucher_Quarter INT DEFAULT NULL,
  Voucher_Year INT DEFAULT NULL,
  PRIMARY KEY (Voucher_ID),
  UNIQUE KEY Voucher_Number (Voucher_Number),
  KEY Head_of_Accounts_ID (Head_of_Accounts_ID),
  KEY IDX_Vouchers_Euro_Year_Quarter (Voucher_Euro, Voucher_Year, Voucher_Quarter),
  CONSTRAINT Vouchers_ibfk_1 FOREIGN KEY (Head_of_Accounts_ID)
    REFERENCES Head_of_Accounts (Head_of_Accounts_ID)
    ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ============================================================
-- 4. Invoices_Chancery
-- ============================================================
CREATE TABLE IF NOT EXISTS Invoices_Chancery (
  ID INT NOT NULL AUTO_INCREMENT,
  Supplier_ID INT DEFAULT NULL,
  Number VARCHAR(255) DEFAULT NULL,
  Date DATE DEFAULT NULL,
  Total DECIMAL(10,2) DEFAULT NULL,
  Vat DECIMAL(10,2) DEFAULT NULL,
  Quarter INT GENERATED ALWAYS AS (QUARTER(`Date`)) STORED,
  Year INT GENERATED ALWAYS AS (YEAR(`Date`)) STORED,
  Refundable TINYINT(1) DEFAULT NULL,
  Status ENUM('Pending','Processed','Archived') DEFAULT 'Processed',
  Voucher_ID INT DEFAULT NULL,
  Recurring TINYINT(1) DEFAULT '1',
  PRIMARY KEY (ID),
  UNIQUE KEY Invoice_Chancery_No (Number),
  KEY Supplier_ID (Supplier_ID),
  KEY icfk2 (Voucher_ID),
  KEY IDX_IC_Vat_Year_Quarter (Vat, Year, Quarter),
  KEY IDX_IC_Voucher_ID (Voucher_ID),
  CONSTRAINT fk_Invoices_Chancery_1 FOREIGN KEY (Supplier_ID)
    REFERENCES NIF_Codes (Supplier_ID)
    ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT icfk2 FOREIGN KEY (Voucher_ID)
    REFERENCES Vouchers (Voucher_ID)
    ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ============================================================
-- 5. Invoices_Residence
-- ============================================================
CREATE TABLE IF NOT EXISTS Invoices_Residence (
  ID INT NOT NULL AUTO_INCREMENT,
  Supplier_ID INT DEFAULT NULL,
  Number VARCHAR(255) DEFAULT NULL,
  Date DATE DEFAULT NULL,
  Total DECIMAL(10,2) DEFAULT NULL,
  Vat DECIMAL(10,2) DEFAULT NULL,
  Quarter INT GENERATED ALWAYS AS (QUARTER(`Date`)) STORED,
  Year INT GENERATED ALWAYS AS (YEAR(`Date`)) STORED,
  Refundable TINYINT(1) DEFAULT NULL,
  Status ENUM('Pending','Processed','Archived') DEFAULT 'Processed',
  Voucher_ID INT DEFAULT NULL,
  Recurring TINYINT(1) DEFAULT '1',
  PRIMARY KEY (ID),
  UNIQUE KEY Invoice_Residence_No (Number),
  KEY Supplier_ID (Supplier_ID),
  KEY irfk2 (Voucher_ID),
  KEY IDX_IR_Vat_Year_Quarter (Vat, Year, Quarter),
  KEY IDX_IR_Voucher_ID (Voucher_ID),
  CONSTRAINT Invoices_Residence_ibfk_1 FOREIGN KEY (Supplier_ID)
    REFERENCES NIF_Codes (Supplier_ID)
    ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT irfk2 FOREIGN KEY (Voucher_ID)
    REFERENCES Vouchers (Voucher_ID)
    ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
