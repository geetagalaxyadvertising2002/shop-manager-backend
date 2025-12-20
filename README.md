Shop Manager Backend
This is the backend for the Shop Manager application, a digital solution for shopkeepers to manage their business operations, including billing, stock management, customer records, and sales reports.
Features

Authentication: User registration and login with token-based authentication.
Shop Management: Manage shop details and associate with users.
Product Management: Add, update, and track product stock with barcode support.
Billing: Create invoices for online and offline sales, with automatic stock updates.
Customer Management: Maintain customer records and track credit (khata) accounts.
Reports: Generate sales and stock reports for business insights.

Setup Instructions

Clone the repository:git clone <repository-url>
cd shop_manager_backend


Create a virtual environment:python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate


Install dependencies:pip install -r requirements.txt


Set up environment variables:
Create a .env file in the root directory (see .env template).
Add SECRET_KEY, DEBUG, DATABASE_URL, and ALLOWED_HOSTS.


Run migrations:python manage.py makemigrations
python manage.py migrate


Create a superuser (for admin access):python manage.py createsuperuser


Run the development server:python manage.py runserver



API Endpoints

Core: /api/core/register/, /api/core/login/, /api/core/profile/
Shop: /api/shop/products/, /api/shop/invoices/, /api/shop/products/low_stock/
Customers: /api/customers/customers/, /api/customers/khatas/
Reports: /api/reports/sales/, /api/reports/stock/

Requirements

Python 3.8+
Django 4.2
Django REST Framework 3.14
python-dotenv 1.0

Notes

Ensure the database is properly configured in settings.py or via DATABASE_URL.
Use token authentication for API requests (obtain token via /api/core/login/).
"# shop-manager-backend" 
