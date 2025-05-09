#!/usr/bin/env python3
"""
Tests for the settings_loader module.

These tests validate the loading and merging of settings from different levels.
"""

import os
import unittest
import json
import tempfile
import shutil
from decimal import Decimal

# Add the parent directory to the path so we can import the module
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from reconciliation.settings_loader import (
    load_json,
    deep_merge,
    load_portfolio_settings,
    load_property_settings,
    load_tenant_settings,
    merge_settings
)


class TestSettingsLoader(unittest.TestCase):
    """Test cases for the settings_loader module."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create a temporary directory for test files
        self.test_dir = tempfile.mkdtemp()
        
        # Create the necessary directory structure
        os.makedirs(os.path.join(self.test_dir, 'Data', 'ProcessedOutput', 'PortfolioSettings'), exist_ok=True)
        os.makedirs(os.path.join(self.test_dir, 'Data', 'ProcessedOutput', 'PropertySettings', 'TEST'), exist_ok=True)
        os.makedirs(os.path.join(self.test_dir, 'Data', 'ProcessedOutput', 'PropertySettings', 'TEST', 'TenantSettings'), exist_ok=True)
        
        # Create test settings files
        self.create_test_settings()
    
    def tearDown(self):
        """Tear down test fixtures."""
        # Remove the temporary directory and its contents
        shutil.rmtree(self.test_dir)
    
    def create_test_settings(self):
        """Create test settings files."""
        # Portfolio settings
        portfolio_settings = {
            "name": "Test Portfolio",
            "settings": {
                "gl_inclusions": {
                    "ret": ["5010", "5020"],
                    "cam": ["6010", "6020"],
                    "admin_fee": ["7010"]
                },
                "admin_fee_percentage": 0.15,
                "prorate_share_method": "RSF",
                "base_year": "2022",
                "cap_settings": {
                    "cap_percentage": 0.05,
                    "cap_type": "previous_year"
                }
            }
        }
        
        # Property settings
        property_settings = {
            "property_id": "TEST",
            "name": "Test Property",
            "total_rsf": 100000,
            "settings": {
                "gl_inclusions": {
                    "ret": ["5030"]  # Override portfolio setting
                },
                "admin_fee_percentage": 0.10,  # Override portfolio setting
                "stop_amount": 7.50  # New setting not in portfolio
            }
        }
        
        # Tenant settings
        tenant_settings = {
            "tenant_id": 1001,
            "name": "Test Tenant",
            "property_id": "TEST",
            "lease_start": "01/01/2023",
            "lease_end": "12/31/2025",
            "settings": {
                "prorate_share_method": "Fixed",  # Override property setting
                "fixed_pyc_share": 5.25,  # New setting not in property
                "base_year": "2023"  # Override portfolio setting
            }
        }
        
        # Write the settings files
        with open(os.path.join(self.test_dir, 'Data', 'ProcessedOutput', 'PortfolioSettings', 'portfolio_settings.json'), 'w') as f:
            json.dump(portfolio_settings, f)
        
        with open(os.path.join(self.test_dir, 'Data', 'ProcessedOutput', 'PropertySettings', 'TEST', 'property_settings.json'), 'w') as f:
            json.dump(property_settings, f)
        
        with open(os.path.join(self.test_dir, 'Data', 'ProcessedOutput', 'PropertySettings', 'TEST', 'TenantSettings', 'Test Tenant - 1001.json'), 'w') as f:
            json.dump(tenant_settings, f)
    
    def test_deep_merge(self):
        """Test the deep_merge function."""
        dict1 = {
            "a": 1,
            "b": {
                "c": 2,
                "d": 3
            }
        }
        
        dict2 = {
            "b": {
                "c": 4,  # Override
                "e": 5   # New nested key
            },
            "f": 6       # New top-level key
        }
        
        merged = deep_merge(dict1, dict2)
        
        self.assertEqual(merged["a"], 1)
        self.assertEqual(merged["b"]["c"], 4)  # Should be overridden
        self.assertEqual(merged["b"]["d"], 3)  # Should be preserved
        self.assertEqual(merged["b"]["e"], 5)  # Should be added
        self.assertEqual(merged["f"], 6)       # Should be added
    
    def test_load_portfolio_settings(self):
        """Test loading portfolio settings."""
        # Mock the settings path
        original_path = reconciliation.settings_loader.PORTFOLIO_SETTINGS_PATH
        reconciliation.settings_loader.PORTFOLIO_SETTINGS_PATH = os.path.join(
            self.test_dir, 'Data', 'ProcessedOutput', 'PortfolioSettings', 'portfolio_settings.json'
        )
        
        try:
            settings = load_portfolio_settings()
            
            # Check basic properties
            self.assertEqual(settings["name"], "Test Portfolio")
            self.assertEqual(settings["settings"]["admin_fee_percentage"], 0.15)
            self.assertEqual(settings["settings"]["gl_inclusions"]["ret"], ["5010", "5020"])
        finally:
            # Restore the original path
            reconciliation.settings_loader.PORTFOLIO_SETTINGS_PATH = original_path
    
    def test_load_property_settings(self):
        """Test loading property settings."""
        # Mock the settings path
        original_path = reconciliation.settings_loader.PROPERTY_SETTINGS_BASE_PATH
        reconciliation.settings_loader.PROPERTY_SETTINGS_BASE_PATH = os.path.join(
            self.test_dir, 'Data', 'ProcessedOutput', 'PropertySettings'
        )
        
        try:
            settings = load_property_settings("TEST")
            
            # Check basic properties
            self.assertEqual(settings["property_id"], "TEST")
            self.assertEqual(settings["name"], "Test Property")
            self.assertEqual(settings["total_rsf"], 100000)
            self.assertEqual(settings["settings"]["admin_fee_percentage"], 0.10)
        finally:
            # Restore the original path
            reconciliation.settings_loader.PROPERTY_SETTINGS_BASE_PATH = original_path
    
    def test_load_tenant_settings(self):
        """Test loading tenant settings."""
        # Mock the settings path
        original_path = reconciliation.settings_loader.PROPERTY_SETTINGS_BASE_PATH
        reconciliation.settings_loader.PROPERTY_SETTINGS_BASE_PATH = os.path.join(
            self.test_dir, 'Data', 'ProcessedOutput', 'PropertySettings'
        )
        
        try:
            settings = load_tenant_settings("TEST", "1001")
            
            # Check basic properties
            self.assertEqual(settings["tenant_id"], 1001)
            self.assertEqual(settings["name"], "Test Tenant")
            self.assertEqual(settings["property_id"], "TEST")
            self.assertEqual(settings["settings"]["prorate_share_method"], "Fixed")
            self.assertEqual(settings["settings"]["fixed_pyc_share"], 5.25)
        finally:
            # Restore the original path
            reconciliation.settings_loader.PROPERTY_SETTINGS_BASE_PATH = original_path
    
    def test_merge_settings(self):
        """Test merging settings from all levels."""
        # Mock the settings paths
        original_portfolio_path = reconciliation.settings_loader.PORTFOLIO_SETTINGS_PATH
        original_property_path = reconciliation.settings_loader.PROPERTY_SETTINGS_BASE_PATH
        
        reconciliation.settings_loader.PORTFOLIO_SETTINGS_PATH = os.path.join(
            self.test_dir, 'Data', 'ProcessedOutput', 'PortfolioSettings', 'portfolio_settings.json'
        )
        reconciliation.settings_loader.PROPERTY_SETTINGS_BASE_PATH = os.path.join(
            self.test_dir, 'Data', 'ProcessedOutput', 'PropertySettings'
        )
        
        try:
            # Test merging at property level (without tenant)
            property_merged = merge_settings("TEST")
            
            # Portfolio settings should be overridden by property settings
            self.assertEqual(property_merged["settings"]["admin_fee_percentage"], 0.10)  # From property
            self.assertEqual(property_merged["settings"]["gl_inclusions"]["ret"], ["5030"])  # From property
            self.assertEqual(property_merged["settings"]["gl_inclusions"]["cam"], ["6010", "6020"])  # From portfolio
            self.assertEqual(property_merged["settings"]["stop_amount"], 7.50)  # From property
            self.assertEqual(property_merged["settings"]["base_year"], "2022")  # From portfolio
            
            # Test merging at tenant level
            tenant_merged = merge_settings("TEST", "1001")
            
            # Tenant settings should override property and portfolio settings
            self.assertEqual(tenant_merged["settings"]["admin_fee_percentage"], 0.10)  # From property
            self.assertEqual(tenant_merged["settings"]["prorate_share_method"], "Fixed")  # From tenant
            self.assertEqual(tenant_merged["settings"]["fixed_pyc_share"], 5.25)  # From tenant
            self.assertEqual(tenant_merged["settings"]["base_year"], "2023")  # From tenant
            self.assertEqual(tenant_merged["settings"]["stop_amount"], 7.50)  # From property
            self.assertEqual(tenant_merged["tenant_id"], 1001)  # From tenant
            self.assertEqual(tenant_merged["lease_start"], "01/01/2023")  # From tenant
        finally:
            # Restore the original paths
            reconciliation.settings_loader.PORTFOLIO_SETTINGS_PATH = original_portfolio_path
            reconciliation.settings_loader.PROPERTY_SETTINGS_BASE_PATH = original_property_path


if __name__ == '__main__':
    unittest.main()