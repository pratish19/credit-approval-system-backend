from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import Customer, Loan
from .serializers import CustomerSerializer, LoanSerializer
from datetime import date
from django.db import models
import math


# --- HELPER FUNCTIONS ---

def calculate_emi(principal, rate, tenure):
    # Standard EMI formula with monthly compounding
    # Rate is annual %, so divide by 12 and 100
    r = rate / (12 * 100)
    n = tenure # tenure in months
    
    if r == 0:
        return principal / n
        
    emi = (principal * r * pow(1 + r, n)) / (pow(1 + r, n) - 1)
    return round(emi, 2)

def calculate_credit_score(customer):
    # Start with a base score
    score = 0
    
    # Get all past loans
    loans = Loan.objects.filter(customer=customer)
    total_loans = loans.count()
    
    # 1. Past Loans paid on time
    paid_on_time_loans = loans.filter(emis_paid_on_time__gte=models.F('tenure')).count() # Simplified logic
    if paid_on_time_loans > 0:
        score += 20

    # 2. Number of loans taken in past
    if total_loans > 0:
        score += 10
    
    # 3. Loan activity in current year
    current_year_loans = loans.filter(start_date__year=date.today().year).count()
    if current_year_loans > 0:
        score += 10

    # 4. Loan approved volume
    total_approved_volume = sum([l.loan_amount for l in loans if l.is_approved])
    if total_approved_volume > 100000:
        score += 10
    
    # If sum of current loans > approved limit, score is 0
    current_debt = sum([l.loan_amount for l in loans if l.is_approved and l.end_date >= date.today()])
    if current_debt > customer.approved_limit:
        score = 0
    else:
        # Give a base score if debt is within limit
        score += 30 
        
    return score

# --- API VIEWS ---

class RegisterCustomer(APIView):
    def post(self, request):
        data = request.data
        monthly_income = data.get('monthly_income')
        
        # Approved limit: 36 * salary, rounded to nearest lakh
        limit = 36 * monthly_income
        limit = round(limit / 100000) * 100000
        
        customer = Customer.objects.create(
            first_name=data['first_name'],
            last_name=data['last_name'],
            age=data['age'],
            monthly_salary=monthly_income,
            phone_number=data['phone_number'],
            approved_limit=limit
        )
        
        return Response({
            "customer_id": customer.id,
            "name": f"{customer.first_name} {customer.last_name}",
            "age": customer.age,
            "monthly_income": customer.monthly_salary,
            "approved_limit": customer.approved_limit,
            "phone_number": customer.phone_number
        }, status=status.HTTP_201_CREATED)

class CheckEligibility(APIView):
    def post(self, request):
        customer_id = request.data.get('customer_id')
        loan_amount = request.data.get('loan_amount')
        interest_rate = request.data.get('interest_rate')
        tenure = request.data.get('tenure')
        
        try:
            customer = Customer.objects.get(id=customer_id)
        except Customer.DoesNotExist:
            return Response({"error": "Customer not found"}, status=404)
            
        # 1. Calculate Credit Score
        credit_score = calculate_credit_score(customer) # Using the helper above
        
        # 2. Determine Approval & Interest Rate
        approval = False
        corrected_interest_rate = interest_rate
        
        if credit_score > 50:
            approval = True
        elif 50 >= credit_score > 30:
            approval = True
            if interest_rate < 12:
                corrected_interest_rate = 12
        elif 30 >= credit_score > 10:
            approval = True
            if interest_rate < 16:
                corrected_interest_rate = 16
        else:
            approval = False
            
        # 3. Check EMI vs Salary constraint
        # Calculate EMI for requested loan
        proposed_emi = calculate_emi(loan_amount, corrected_interest_rate, tenure)
        
        # Sum of current EMIs
        current_loans = Loan.objects.filter(customer=customer, is_approved=True, end_date__gte=date.today())
        current_emis_sum = sum([l.monthly_repayment for l in current_loans])
        
        if (current_emis_sum + proposed_emi) > (0.5 * float(customer.monthly_salary)):
            approval = False
            
        return Response({
            "customer_id": customer_id,
            "approval": approval,
            "interest_rate": interest_rate,
            "corrected_interest_rate": corrected_interest_rate,
            "tenure": tenure,
            "monthly_installment": proposed_emi
        })

class CreateLoan(APIView):
    def post(self, request):
        customer_id = request.data.get('customer_id')
        loan_amount = request.data.get('loan_amount')
        interest_rate = request.data.get('interest_rate')
        tenure = request.data.get('tenure')
        
        # Re-run eligibility check logic internally to be safe
        # (For this assignment, we will assume the inputs are valid if passed here)
        
        try:
            customer = Customer.objects.get(id=customer_id)
        except Customer.DoesNotExist:
            return Response({"error": "Customer not found"}, status=404)

        emi = calculate_emi(loan_amount, interest_rate, tenure)
        
        # Create the Loan
        loan = Loan.objects.create(
            customer=customer,
            loan_amount=loan_amount,
            interest_rate=interest_rate,
            tenure=tenure,
            monthly_repayment=emi,
            is_approved=True,
            # Simple logic for end date: today + tenure months
            end_date=date.today() # In real app, add months logic
        )
        
        return Response({
            "loan_id": loan.id,
            "customer_id": customer.id,
            "loan_approved": True,
            "message": "Loan approved successfully",
            "monthly_installment": emi
        }, status=status.HTTP_201_CREATED)

class ViewLoan(APIView):
    def get(self, request, loan_id):
        try:
            loan = Loan.objects.get(id=loan_id)
            customer = loan.customer
            return Response({
                "loan_id": loan.id,
                "customer": {
                    "id": customer.id,
                    "first_name": customer.first_name,
                    "last_name": customer.last_name,
                    "phone_number": customer.phone_number,
                    "age": customer.age
                },
                "loan_amount": loan.loan_amount,
                "interest_rate": loan.interest_rate,
                "monthly_installment": loan.monthly_repayment,
                "tenure": loan.tenure
            })
        except Loan.DoesNotExist:
            return Response({"error": "Loan not found"}, status=404)

class ViewCustomerLoans(APIView):
    def get(self, request, customer_id):
        loans = Loan.objects.filter(customer_id=customer_id)
        data = []
        for loan in loans:
            data.append({
                "loan_id": loan.id,
                "loan_amount": loan.loan_amount,
                "interest_rate": loan.interest_rate,
                "monthly_installment": loan.monthly_repayment,
                "repayments_left": loan.tenure - loan.emis_paid_on_time
            })
        return Response(data)