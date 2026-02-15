from celery import shared_task
import pandas as pd
from .models import Customer, Loan
import os

@shared_task
def ingest_customer_data():
    # Check if file exists
    if not os.path.exists('customer_data.xlsx'):
        print("Error: customer_data.xlsx not found!")
        return

    df = pd.read_excel('customer_data.xlsx')
    for _, row in df.iterrows():
        # Calculate approved limit based on formula
        limit = 36 * row['Monthly Salary']
        limit = round(limit / 100000) * 100000

        Customer.objects.create(
            first_name=row['First Name'],
            last_name=row['Last Name'],
            age=row['Age'],
            phone_number=row['Phone Number'],
            monthly_salary=row['Monthly Salary'],
            approved_limit=limit,
            current_debt=0 
        )
    print("Customer Data Ingested Successfully")

@shared_task
def ingest_loan_data():
    if not os.path.exists('loan_data.xlsx'):
        print("Error: loan_data.xlsx not found!")
        return

    df = pd.read_excel('loan_data.xlsx')
    for _, row in df.iterrows():
        try:
            customer = Customer.objects.get(pk=row['Customer ID'])
            Loan.objects.create(
                customer=customer,
                loan_amount=row['Loan Amount'],
                tenure=row['Tenure'],
                interest_rate=row['Interest Rate'],
                monthly_repayment=row['Monthly payment'],
                emis_paid_on_time=row['EMIs paid on time'],
                start_date=row['Date of Approval'],
                end_date=row['End Date'],
                is_approved=True 
            )
        except Customer.DoesNotExist:
            print(f"Skipping loan for unknown customer ID: {row['Customer ID']}")
    print("Loan Data Ingested Successfully")