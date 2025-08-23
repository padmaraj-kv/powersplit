"""
Data encryption utilities for sensitive information (Requirement 8.1)
"""
import base64
import logging
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from app.core.config import settings
from typing import Optional

logger = logging.getLogger(__name__)


class DataEncryption:
    """Handles encryption and decryption of sensitive data"""
    
    def __init__(self):
        self._fernet = self._create_fernet()
    
    def _create_fernet(self) -> Fernet:
        """Create Fernet instance from encryption key"""
        try:
            # Use the encryption key from settings
            key = settings.encryption_key.encode()
            
            # If key is not 32 bytes, derive it using PBKDF2
            if len(key) != 32:
                kdf = PBKDF2HMAC(
                    algorithm=hashes.SHA256(),
                    length=32,
                    salt=b'bill_splitting_salt',  # Static salt for consistency
                    iterations=100000,
                )
                key = base64.urlsafe_b64encode(kdf.derive(key))
            else:
                key = base64.urlsafe_b64encode(key)
            
            return Fernet(key)
        except Exception as e:
            logger.error(f"Failed to create encryption instance: {e}")
            raise
    
    def encrypt(self, data: str) -> str:
        """Encrypt sensitive data"""
        try:
            if not data:
                return data
            
            encrypted_data = self._fernet.encrypt(data.encode())
            return base64.urlsafe_b64encode(encrypted_data).decode()
        except Exception as e:
            logger.error(f"Encryption failed: {e}")
            raise
    
    def decrypt(self, encrypted_data: str) -> str:
        """Decrypt sensitive data"""
        try:
            if not encrypted_data:
                return encrypted_data
            
            decoded_data = base64.urlsafe_b64decode(encrypted_data.encode())
            decrypted_data = self._fernet.decrypt(decoded_data)
            return decrypted_data.decode()
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            raise
    
    def encrypt_phone_number(self, phone_number: str) -> str:
        """Encrypt phone number for storage"""
        return self.encrypt(phone_number)
    
    def decrypt_phone_number(self, encrypted_phone: str) -> str:
        """Decrypt phone number for use"""
        return self.decrypt(encrypted_phone)
    
    def encrypt_contact_info(self, contact_data: dict) -> dict:
        """Encrypt sensitive contact information"""
        encrypted_data = contact_data.copy()
        
        # Encrypt phone number
        if 'phone_number' in encrypted_data:
            encrypted_data['phone_number'] = self.encrypt_phone_number(encrypted_data['phone_number'])
        
        # Encrypt name if it contains sensitive information
        if 'name' in encrypted_data and encrypted_data['name']:
            encrypted_data['name'] = self.encrypt(encrypted_data['name'])
        
        return encrypted_data
    
    def decrypt_contact_info(self, encrypted_data: dict) -> dict:
        """Decrypt sensitive contact information"""
        decrypted_data = encrypted_data.copy()
        
        # Decrypt phone number
        if 'phone_number' in decrypted_data:
            decrypted_data['phone_number'] = self.decrypt_phone_number(decrypted_data['phone_number'])
        
        # Decrypt name
        if 'name' in decrypted_data and decrypted_data['name']:
            decrypted_data['name'] = self.decrypt(decrypted_data['name'])
        
        return decrypted_data


# Global encryption instance
encryption = DataEncryption()


def encrypt_sensitive_data(data: str) -> str:
    """Convenience function for encrypting sensitive data"""
    return encryption.encrypt(data)


def decrypt_sensitive_data(encrypted_data: str) -> str:
    """Convenience function for decrypting sensitive data"""
    return encryption.decrypt(encrypted_data)