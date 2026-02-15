from django.urls import path
from .views import RegisterCustomer, CheckEligibility, CreateLoan, ViewLoan, ViewCustomerLoans

urlpatterns = [
    path('register', RegisterCustomer.as_view()),
    path('check-eligibility', CheckEligibility.as_view()),
    path('create-loan', CreateLoan.as_view()),
    path('view-loan/<int:loan_id>', ViewLoan.as_view()),
    path('view-loans/<int:customer_id>', ViewCustomerLoans.as_view()),
]