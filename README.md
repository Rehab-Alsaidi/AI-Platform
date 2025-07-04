# 51Talk AI Learning Platform

A comprehensive Flask-based learning management system with AI-powered assistance, multilingual support, and quiz functionality. This platform provides interactive learning experiences with document-based Q&A, team management, progress tracking, and administrative tools.

![Platform Preview](https://img.shields.io/badge/Python-3.8+-blue.svg)
![Flask](https://img.shields.io/badge/Flask-2.3+-green.svg)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-13+-blue.svg)
![Docker](https://img.shields.io/badge/Docker-Compose-blue.svg)

## 🌟 Features

### 🎓 Learning Management
- **Interactive Units**: Structured learning units with materials, videos, vocabulary, and projects
- **AI Vocabulary System**: Detailed word explanations with metaphors, visual explanations, and real-world connections
- **Progress Tracking**: Comprehensive user progress monitoring with completion percentages
- **Project Submissions**: File upload system for project assignments

### 🧠 AI-Powered Features
- **Document Q&A**: AI assistant powered by Llama model for course material questions
- **Multilingual Support**: English, Chinese (中文), and Arabic (العربية) interface
- **Smart Responses**: Context-aware answers based on uploaded course documents

### 📝 Assessment System
- **One-Time Quizzes**: Single-attempt quiz system with comprehensive review
- **Detailed Feedback**: Question-by-question explanations and correct answer highlighting
- **Scoring System**: Automatic grading with pass/fail determination
- **Review Mode**: Post-quiz review showing user answers vs. correct answers

### 👥 Team Management
- **Team Creation**: Organize users into teams (Middle East and Chinese camps)
- **Team Scoring**: Automatic team score updates based on individual performance
- **Leaderboards**: Team ranking systems for competitive learning

### 🔐 User Management
- **Secure Authentication**: Email verification, password reset functionality
- **Role-Based Access**: User and admin role separation
- **Profile Management**: User language preferences and settings

### 📊 Administrative Tools
- **Content Management**: Add/edit quizzes, materials, videos, projects, and vocabulary
- **User Analytics**: Export user data, progress reports, and feedback
- **Document Management**: Upload and manage course materials for AI assistant
- **System Monitoring**: Statistics dashboard and user activity tracking

## 🛠️ Technology Stack

- **Backend**: Flask (Python 3.8+)
- **Database**: PostgreSQL 13+
- **AI/ML**: Llama 3 model integration for Q&A
- **Frontend**: Bootstrap 5, Jinja2 templates
- **Email**: Flask-Mail for notifications
- **File Processing**: PDF, PowerPoint, Word document support
- **Containerization**: Docker & Docker Compose
- **Authentication**: Werkzeug security utilities

## 📋 Prerequisites

- **Docker & Docker Compose**: Latest stable versions
- **Python 3.8+**: For local development (optional)
- **Git**: For cloning the repository

## 🚀 Quick Setup Guide

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/51talk-ai-learning.git
cd 51talk-ai-learning
```

### 2. Environment Configuration

Create a `.env` file in the project root:

```bash
# Database Configuration
DB_HOST=localhost
DB_PORT=5432
DB_NAME=fiftyone_learning
DB_USER=admin
DB_PASSWORD=admin123

# Flask Configuration
FLASK_SECRET_KEY=your-super-secret-key-here
ACCESS_PASSWORD=5151

# Email Configuration (Optional - for email verification)
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-app-password
MAIL_DEFAULT_SENDER=your-email@gmail.com

# AI Model Configuration
LLAMA_MODEL_PATH=models/Meta-Llama-3-8B-Instruct-Q4_K_M.gguf
```

### 3. Docker Compose Setup

Create a `docker-compose.yml` file:

```yaml
version: '3.8'

services:
  postgres:
    image: postgres:13
    container_name: fiftyone_postgres
    environment:
      POSTGRES_DB: fiftyone_learning
      POSTGRES_USER: admin
      POSTGRES_PASSWORD: admin123
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./init.sql:/docker-entrypoint-initdb.d/init.sql
    restart: unless-stopped

  web:
    build: .
    container_name: fiftyone_web
    ports:
      - "5000:5000"
    environment:
      - DB_HOST=postgres
      - DB_PORT=5432
      - DB_NAME=fiftyone_learning
      - DB_USER=admin
      - DB_PASSWORD=admin123
    volumes:
      - ./static/uploads:/app/static/uploads
      - ./documents:/app/documents
      - ./models:/app/models
    depends_on:
      - postgres
    restart: unless-stopped

volumes:
  postgres_data:
```

### 4. Create Dockerfile

```dockerfile
FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p static/uploads documents models

# Expose port
EXPOSE 5000

# Run the application
CMD ["python", "app.py"]
```

### 5. Install Dependencies

Create a `requirements.txt` file:

```txt
Flask==2.3.3
Flask-Mail==0.9.1
psycopg2-binary==2.9.7
python-dotenv==1.0.0
Werkzeug==2.3.7
```

### 6. Launch the Application

```bash
# Build and start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Check running containers
docker-compose ps
```

### 7. Access the Application

- **Web Application**: http://localhost:5000
- **Default Access Password**: `5151`
- **Admin Panel**: http://localhost:5000/admin
- **Default Admin Credentials**: `admin` / `admin123`

## 📁 Project Structure

```
51talk-ai-learning/
├── app.py                    # Main Flask application
├── init.sql                  # Database initialization script
├── qa.py                     # Simple Q&A system
├── enhanced_document_qa.py   # Advanced document Q&A with Llama
├── docker-compose.yml        # Docker Compose configuration
├── Dockerfile               # Docker container configuration
├── requirements.txt         # Python dependencies
├── .env                     # Environment variables
├── README.md               # This file
├── static/
│   ├── uploads/            # User uploaded files
│   └── css/               # Custom stylesheets
├── templates/
│   ├── base.html          # Base template
│   ├── dashboard.html     # User dashboard
│   ├── unit.html          # Learning unit page
│   ├── quiz.html          # Quiz taking interface
│   ├── quiz_review.html   # Quiz review page
│   └── admin/             # Admin templates
└── documents/             # Course materials for AI assistant
```

## 🔧 Configuration

### Database Setup

The application automatically initializes the database using `init.sql`. The script creates:

- User management tables
- Learning content tables (units, quizzes, materials, videos, words)
- Progress tracking tables
- Team management tables
- Q&A history tables
- Admin tables

### AI Model Setup (Optional)

For AI-powered Q&A functionality:

1. **Download Llama Model** (optional):
   ```bash
   mkdir models
   # Download Meta-Llama-3-8B-Instruct-Q4_K_M.gguf to models/ directory
   ```

2. **Add Course Documents**:
   - Place PDF, PPT, PPTX, or TXT files in the `documents/` directory
   - The AI assistant will automatically process these files

### Email Configuration (Optional)

For email verification and password reset:

1. **Gmail Setup**:
   - Enable 2-factor authentication
   - Generate an app-specific password
   - Update `.env` with your credentials

## 👨‍💼 Admin Features

### Content Management

1. **Access Admin Panel**: http://localhost:5000/admin
2. **Add Learning Content**:
   - **Quizzes**: Create multiple-choice questions with explanations
   - **Materials**: Upload PDF, PPT, Word documents
   - **Videos**: Add YouTube video links
   - **Vocabulary**: Create detailed AI-powered word explanations
   - **Projects**: Define project assignments

### User Management

- **View Users**: Monitor user registration and activity
- **Export Data**: Download user progress and feedback as CSV
- **Team Management**: Create and manage learning teams
- **Score Management**: Update team scores manually

### System Monitoring

- **Dashboard**: View system statistics and user activity
- **Document Management**: Upload course materials for AI assistant
- **Database Tools**: Reset data, export reports

## 🎯 Usage Guide

### For Students

1. **Registration**: Create account with email verification
2. **Learning Path**:
   - Study materials and videos
   - Learn AI vocabulary with detailed explanations
   - Complete projects
   - Take one-time quizzes
   - Review quiz results with explanations
3. **AI Assistant**: Ask questions about course materials
4. **Progress Tracking**: Monitor completion status

### For Instructors/Admins

1. **Content Creation**: Add learning materials through admin panel
2. **Student Monitoring**: Track progress and performance
3. **Team Management**: Organize students into competitive teams
4. **Assessment Review**: Monitor quiz performance and feedback

## 🔍 API Endpoints

### Public Endpoints
- `GET /`: Password gate
- `POST /login`: User authentication
- `POST /register`: User registration

### Protected Endpoints
- `GET /dashboard`: User dashboard
- `GET /unit/<id>`: Learning unit view
- `GET /quiz/<id>`: Quiz interface
- `POST /ask_ai`: AI assistant queries

### Admin Endpoints
- `GET /admin/dashboard`: Admin dashboard
- `GET /admin/users`: User management
- `POST /admin/add_quiz`: Create quiz
- `POST /admin/add_material`: Upload materials

## 🚨 Troubleshooting

### Common Issues

1. **Database Connection Failed**:
   ```bash
   # Check if PostgreSQL container is running
   docker-compose ps
   
   # Restart PostgreSQL
   docker-compose restart postgres
   ```

2. **Quiz Responses Not Saving**:
   ```bash
   # Check if quiz_responses table exists
   docker exec -i fiftyone_postgres psql -U admin -d fiftyone_learning -c "\dt quiz_responses"
   
   # If missing, run the missing table creation script
   docker exec -i fiftyone_postgres psql -U admin -d fiftyone_learning -f /docker-entrypoint-initdb.d/init.sql
   ```

3. **AI Assistant Not Working**:
   - Ensure documents are placed in `documents/` directory
   - Check if Llama model is downloaded (optional)
   - Verify document file formats (PDF, PPT, PPTX, TXT)

4. **Email Verification Issues**:
   - Check email configuration in `.env`
   - Verify Gmail app password setup
   - Check spam folder for verification emails

### Database Management

```bash
# Access PostgreSQL directly
docker exec -it fiftyone_postgres psql -U admin -d fiftyone_learning

# Backup database
docker exec fiftyone_postgres pg_dump -U admin fiftyone_learning > backup.sql

# Reset specific user quiz attempts
docker exec -i fiftyone_postgres psql -U admin -d fiftyone_learning -c "
DELETE FROM quiz_attempts WHERE user_id = [USER_ID] AND unit_id = [UNIT_ID];
"
```

### Performance Optimization

1. **Large Document Processing**: Place smaller, focused documents in the `documents/` directory
2. **Database Performance**: Regularly monitor query performance for large user bases
3. **File Storage**: Configure external storage for uploaded files in production

## 🔒 Security Considerations

- **Environment Variables**: Never commit `.env` files to version control
- **Password Security**: Use strong, unique passwords for database and admin accounts
- **File Uploads**: Validate file types and scan for malicious content
- **Database Access**: Restrict database access to application containers only
- **HTTPS**: Use HTTPS in production environments

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Commit changes: `git commit -am 'Add feature'`
4. Push to branch: `git push origin feature-name`
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 📞 Support

For technical support or questions:

- **Issues**: Create a GitHub issue
- **Documentation**: Check this README and inline code comments
- **Community**: Join our discussions in the GitHub repository

## 🔄 Updates and Roadmap

### Recent Updates
- ✅ One-time quiz system with comprehensive review
- ✅ AI-powered vocabulary explanations
- ✅ Team management and scoring
- ✅ Multilingual interface support
- ✅ Document-based AI assistant

### Planned Features
- 🔄 Mobile-responsive design improvements
- 🔄 Advanced analytics dashboard
- 🔄 Integration with external LMS platforms
- 🔄 Real-time collaborative features
- 🔄 Advanced AI model fine-tuning

---

**Happy Learning! 🎓✨**

For more information, visit our [GitHub repository](https://github.com/yourusername/51talk-ai-learning) or contact the development team.
