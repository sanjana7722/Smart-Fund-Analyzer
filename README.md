# Smart Fund Analyzer

An intelligent web application that provides personalized mutual fund recommendations using machine learning algorithms and AI-powered chat assistance.

## 🚀 Live Demo

👉 [Click here to use the app]([https://your-app-name.streamlit.app](https://smart-fund-analyzer-ek3bgbm3qdr3mrtbv5minq.streamlit.app/))

## Features

- **Personalized Recommendations**: Get tailored mutual fund suggestions based on your age, income, risk appetite, investment goals, and duration.
- **AI Chat Assistant**: Interact with an AI advisor powered by OpenAI GPT for investment guidance and explanations.
- **Portfolio Analysis**: View detailed portfolio allocations, expected returns, and risk assessments.
- **Fund Scoring**: Advanced scoring system using multiple ML models including ARIMA forecasting, decision trees, and custom recommendation algorithms.
- **Admin Dashboard**: Secure admin panel for managing the application and viewing analytics.
- **Interactive Visualizations**: Charts and graphs for fund performance, allocation breakdowns, and market insights.
- **Tax-Saving Options**: Filter for tax-saving mutual funds (ELSS).
- **ESG Preferences**: Include environmentally and socially responsible investment options.

## Tech Stack

- **Frontend**: Streamlit
- **Backend**: Python
- **ML Models**: Scikit-learn, Statsmodels, Joblib
- **Data Processing**: Pandas, NumPy
- **Visualization**: Matplotlib, Altair
- **AI Integration**: OpenAI API
- **Database**: SQLite (for feedback storage)

## Installation

### Prerequisites

- Python 3.8 or higher
- pip package manager

### Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/sanjana7722/Smart-Fund-Analyzer.git
   cd Smart-Fund-Analyzer
   ```

2. **Create a virtual environment:**
   ```bash
   python -m venv .venv
   .venv\Scripts\activate  # On Windows
   # or
   source .venv/bin/activate  # On macOS/Linux
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables:**
   - Copy `.env` file and add your API keys:
   ```bash
   cp .env .env  # If not present, create it
   ```
   - Edit `.env` and add:
   ```
   OPENAI_API_KEY=your_openai_api_key_here
   ADMIN_PASSWORD=your_secure_admin_password
   ```

## Usage

1. **Run the application:**
   ```bash
   streamlit run app.py
   ```

2. **Access the app:**
   - Open your browser and go to `http://localhost:8501`

3. **Using the app:**
   - Fill in your profile information (age, income, risk appetite, etc.)
   - Get personalized fund recommendations
   - Chat with the AI advisor for more insights
   - Access admin features with the admin password

## Project Structure

```
ai-mutual-fund-platform/
├── app.py                 # Main Streamlit application
├── requirements.txt       # Python dependencies
├── .env                   # Environment variables (not committed)
├── .gitignore            # Git ignore rules
├── LICENSE               # Project license
├── backend/
│   ├── main.py           # Backend API endpoints
│   ├── run_*.py          # ML model runners
│   ├── schemas.py        # Data schemas
│   ├── data/             # Processed data files
│   └── ml/               # Machine learning models
│       ├── allocation_engine.py
│       ├── arima_model.py
│       ├── decision_tree_model.py
│       ├── recommendation_model.py
│       └── scoring.py
├── models/               # Additional model files
└── services/             # Business logic services
    └── recommendation_service.py
```

## ML Models

- **ARIMA Model**: Time series forecasting for fund performance prediction
- **Decision Tree**: Classification for fund suitability based on user profiles
- **Recommendation Engine**: Custom algorithm for fund scoring and ranking
- **Allocation Engine**: Portfolio optimization and asset allocation

## API Keys Setup

The application requires an OpenAI API key for the chat functionality:

1. Get your API key from [OpenAI Platform](https://platform.openai.com/)
2. Add it to your `.env` file as `OPENAI_API_KEY=your_key_here`
3. Never commit API keys to version control

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## Disclaimer

This application is for educational and informational purposes only. It does not constitute financial advice. Always consult with a qualified financial advisor before making investment decisions. Past performance does not guarantee future results.

## Support

For questions or issues:
- Open an issue on GitHub
- Check the FAQs section in the app
- Contact the maintainers

---

Built with ❤️ using Streamlit and Python
