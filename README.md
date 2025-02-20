# MamiBioMed Bot

Telegram bot for managing sales and prepayments for MamiBioMed.

## Features

- Full payment processing
- Prepayment handling
- Prepayment surcharge processing
- Google Sheets integration for data storage
- Secure access with authentication

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Configure environment variables:
Create a `.env` file with:
```
API_TOKEN=your_telegram_token
ACCESS_CODE=your_access_code
```

3. Set up Google Sheets:
- Place your `credentials.json` in the root directory
- Configure the spreadsheet name in `bot.py`

## Usage

Run the bot:
```bash
python bot.py
```

## Commands

- `/start` - Begin interaction with the bot
- Available options after authentication:
  * Полная оплата (Full Payment)
  * Предоплата (Prepayment)
  * Доплата предоплаты (Prepayment Surcharge)
