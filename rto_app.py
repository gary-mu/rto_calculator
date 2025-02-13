import streamlit as st
import math
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import plotly.express as px
from pandas.tseries.holiday import USFederalHolidayCalendar
from openai import OpenAI
import os
databricks_key = st.secrets['general']["DATABRICKS_API_KEY"]
openai_key = st.secrets['general']["OPENAI_API_KEY"]

def get_custom_holidays(start_date, end_date):
    # Get US federal holidays
    cal = USFederalHolidayCalendar()
    holidays = cal.holidays(start=start_date, end=end_date)

    year = start_date.year
    start = pd.to_datetime(start_date)
    end = pd.to_datetime(end_date)

    # Compute the day after Thanksgiving (4th Thursday of November + 1 day)
    thanksgiving = pd.date_range(start=f'{year}-11-01', end=f'{year}-11-30', freq='W-THU')[3]
    christmas = pd.to_datetime(f'{year}-12-25')
    if start <= thanksgiving <= end:
        day_after_thanksgiving = thanksgiving + timedelta(days=1)
        additional_holidays = pd.DatetimeIndex([day_after_thanksgiving])
        holidays = holidays.append(additional_holidays).sort_values()

    if start <= christmas <= end:
    # Compute the day before Christmas (December 24)
        min_end = min(end, pd.to_datetime(f'{year}-12-31'))
        christmas_break = pd.date_range(start=f'{year}-12-24', end=min_end)
        christmas_break = christmas_break[~christmas_break.weekday.isin([5, 6])]
        holidays = holidays.append(christmas_break).sort_values()

    return holidays

def calculate_workdays(start_date, end_date):
    """Calculate number of workdays between two dates, excluding US federal holidays."""
    holidays = get_custom_holidays(start_date, end_date)
    
    # Create date range and convert to dataframe
    date_range = pd.date_range(start=start_date, end=end_date)
    df = pd.DataFrame(index=date_range)
    
    # Filter out weekends and holidays
    workdays = df[~df.index.isin(holidays) & 
                 ~df.index.weekday.isin([5, 6])].shape[0]
    
    return workdays

def calculate_monthly_workdays(start_date, end_date):
    """Calculate workdays for each month in the date range."""
    months = pd.date_range(start=start_date, end=end_date, freq='ME')
    monthly_workdays = {}
    
    for month in months:
        month_start = month.replace(day=1)
        month_end = month
        workdays = calculate_workdays(month_start, month_end)
        monthly_workdays[month.strftime('%Y-%m')] = workdays
    
    return monthly_workdays

def display_metrics_and_charts(monthly_data, monthly_workdays, holidays):
    """Display metrics and charts based on the calculated data."""
    # Display summary metrics
    st.subheader("Summary")
    
    total_holidays = len(holidays)
    total_ptos = st.session_state.total_pto
    total_workdays = sum(monthly_workdays.values()) - total_pto
    total_office_days = sum(row['Office Days Required'] for row in monthly_data)
    avg_monthly_office_days = round(total_office_days / len(monthly_workdays), 1)

    row1_col1, row1_col2, row1_col3 = st.columns(3)
    row1_col1.metric("Company holidays", f"{total_holidays:.1f}")
    row1_col2.metric("Total PTO days", f"{total_ptos:.1f}")
    row1_col3.metric("Total Work Days", f"{total_workdays:.1f}")


    row2_col1, row2_col2, row2_col3 = st.columns(3)
    row2_col1.metric("Total Required Office Days", f"{total_office_days:.1f}")
    row2_col2.metric("Avg Monthly Office Days", f"{avg_monthly_office_days:.1f}")
    
    # Create tabs for table and chart
    chart_tab, table_tab = st.tabs(["Monthly Visualization", "Detailed Monthly Table"])
    
    # Convert data to DataFrame
    df = pd.DataFrame(monthly_data)
    
    # Show chart in first tab
    with chart_tab:
        fig = px.bar(df, 
                    x='Month', 
                    y=['Office Days Required', 'PTO Days'],
                    title='Monthly Office Days Required vs PTO',
                    barmode='group')
        fig.update_layout(
            xaxis_title="Month",
            yaxis_title="Days",
            legend_title="Category",
            height=500  # Make the chart a bit taller
        )
        st.plotly_chart(fig, use_container_width=True)

    # Show table in second tab
    with table_tab:
        st.dataframe(df, hide_index=True, use_container_width=True)
    
    show_ai_button(monthly_data, monthly_workdays, holidays)

def show_ai_button(monthly_data, monthly_workdays, holidays):
    if st.button("AI Suggest PTO Plan"):
        with st.spinner("Thinking...feel free to grab a beverage while you wait"):
            prompt = f"""
            Use the monthly data and holidays to help me optimize my PTO plan.
            Focus on which month I should take PTO to minimize the total office days required.
            Factor in weekends and company holidays to maximize day offs.
            Do not suggest day offs between Christmas and New year since this is already a company holiday.
            Also avoid suggesting taking day off for a whole week if I need to take Monday to Friday off using PTOs.

            Here is the monthly data of how many work days, holidays, PTO days and office days required for each month:
            {monthly_data}

            Here are the company holidays during this period:
            {holidays}

            Use this format for your suggestions:
            **Overall summary**: [summary of the strategy]

            PTO strategy by month:
            - Month: [Month]
             - PTO Days: [Number of PTO Days]
             - Total required office days: [Number of days to go into office subtracting the suggested PTO and holidays]
             - Dates to take: [Dates to take PTO to maximize day offs including weekends and holidays]
            """


            client = OpenAI(
                api_key=openai_key
            )
            chat_completion = client.chat.completions.create(
                messages=[
                    {
                        "role": "system",
                        "content": "You are an AI assistant"
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                model="gpt-4o-mini",
                max_tokens=1256
            )
            output = chat_completion.choices[0].message.content
        
        st.markdown(f"**AI Suggested PTO Plan**:\n {output}")        

def reset_global_var():
    st.session_state.monthly_data = None
    st.session_state.monthly_workdays = None
    st.session_state.total_pto = 0

def init_session_state():
    """Initialize session state variables."""
    if 'reset_specific_pto' not in st.session_state:
        st.session_state.reset_specific_pto = False
    if 'tab' not in st.session_state:
        st.session_state.tab = 'Option1: Avg PTO per month'
    if 'avg_pto' not in st.session_state:
        st.session_state.avg_pto = 1.0
    if 'pto_default_value' not in st.session_state:
        st.session_state.pto_default_value = 0.0
    if 'total_pto' not in st.session_state:
        st.session_state.total_pto = 0.0
    if 'pto_accounting_policy' not in st.session_state:
        st.session_state.pto_accounting_policy = 'PTO subtract from workdays'

#####START OF THE APP ########
init_session_state() # Initialize session state variables

st.title("Return to Office Calculator")
st.write("Calculate your required office days based on the 60% policy")

# Date range selection
col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input("Start Date", datetime(datetime.today().year, 1, 1))
with col2:
    end_date = st.date_input("End Date", datetime(datetime.today().year, 12, 31))


# PTO input
st.subheader("PTO Planning")
st.markdown("**1. Enter number of PTO days you have in this period:**")
total_pto_allowance = st.number_input(
                "Enter PTO allowance for the period",
                min_value=20.0,
                max_value=60.0,
                value=20.0,
                step=0.5,
                key=f"pto_days")

st.markdown("**2. Use default CZI PTO accounting policy**")
pto_accounting_policy = st.radio(
            'Choose how PTO is accounted for', 
            ['PTO subtract from workdays', 'PTO as a day in office'],
            horizontal=True,
            key='pto_accounting_policy', 
            help='By default, PTO is subtracted from work days. Alternative policy is count PTO as a day in office'
)
if st.session_state.pto_accounting_policy != pto_accounting_policy:
    st.session_state.pto_accounting_policy = pto_accounting_policy

st.markdown("**3. Choose how you want to plan your PTO days**")
tab = st.radio(
            "Choose an option:",
            ["Option1: Avg PTO per month", "Option2: PTO for each month"],
            horizontal=True,
            key="pto_selector", 
            index = 0
        )
if st.session_state.tab != tab:
    st.session_state.tab = tab


#Option 1: use average PTO days per month
if st.session_state.tab == "Option1: Avg PTO per month":
    reset_global_var()
    monthly_pto = st.slider("Select average PTO days taken per month", 
                            min_value=0.0, 
                            max_value=7.0, 
                            value=0.0,
                            step=0.5,
                            help="Select average number of PTO days you plan to take per month")
    #Get number of holidays
    holidays = get_custom_holidays(start_date, end_date)

    # Calculate workdays for the entire period
    total_workdays = calculate_workdays(start_date, end_date)
    
    # Calculate monthly breakdown
    monthly_workdays = calculate_monthly_workdays(start_date, end_date)
    
    # Calculate office days (60% of workdays minus PTO)
    months_count = len(monthly_workdays)
    total_pto = monthly_pto * months_count
    st.session_state.total_pto = total_pto
    monthly_pto_avg = monthly_pto
    st.markdown(f"**Total PTO planned in this period: {total_pto:.1f} days**")

    if total_pto <= total_pto_allowance:
        # Calculate monthly data
        monthly_data = []
        for month, workdays in monthly_workdays.items():
            if st.session_state.pto_accounting_policy == 'PTO subtract from workdays':
                net_days = workdays - monthly_pto_avg
                office_days = round(net_days * 0.6, 0)
            else:
                net_days = workdays
                office_days = round(net_days * 0.6, 0) - monthly_pto_avg
            monthly_data.append({
                'Month': pd.to_datetime(month + "-01").strftime("%b %Y"),
                'Work Days': workdays,
                'PTO Days': monthly_pto,
                'Net Work Days': net_days,
                'Office Days Required': office_days
            })
        print(pd.DataFrame(monthly_data))
        display_metrics_and_charts(monthly_data, monthly_workdays, holidays)
    else:
        st.error("Total PTO exceeds allowance!")
        pass

#option 2: PTO for each month
elif st.session_state.tab == "Option2: PTO for each month":
    reset_global_var()
    if start_date and end_date and start_date <= end_date:
        #Get number of holidays
        holidays = get_custom_holidays(start_date, end_date)
        # Calculate monthly workdays
        monthly_workdays = calculate_monthly_workdays(start_date, end_date)
        # Create columns for PTO inputs
        cols_per_row = 4
        monthly_pto = {}
        # Create rows of columns for better layout
        months = list(monthly_workdays.keys())
        for i in range(0, len(months), cols_per_row):
            cols = st.columns(cols_per_row)
            for j, col in enumerate(cols):
                if i + j < len(months):
                    month = months[i + j]
                    # Format month for display (e.g., "2024-01" to "Jan 2024")
                    display_month = pd.to_datetime(month + "-01").strftime("%b %Y")
                    monthly_pto[month] = col.number_input(
                        display_month,
                        min_value=0.0,
                        max_value=float(monthly_workdays[month]),
                        value=st.session_state.pto_default_value,
                        step=0.5,
                        key=f"pto_{month}"
                    )
        # Calculate total PTO
        total_pto = sum(monthly_pto.values())
        st.session_state.total_pto = total_pto
        monthly_pto_avg = total_pto/len(months)
        
        # Display total PTO with warning if over 30 days
        st.markdown(f"**Total PTO planned in this period: {total_pto:.1f} days**")
        
        if total_pto <= total_pto_allowance:
            # Calculate monthly data
            monthly_data = []
            for month, workdays in monthly_workdays.items():
                if st.session_state.pto_accounting_policy == 'PTO subtract from workdays':
                    net_days = workdays - monthly_pto[month]
                    office_days = round(net_days * 0.6, 0)
                else:
                    net_days = workdays
                    office_days = round(net_days * 0.6, 0) - monthly_pto[month]
                monthly_data.append({
                    'Month': pd.to_datetime(month + "-01").strftime("%b %Y"),
                    'Work Days': workdays,
                    'PTO Days': monthly_pto[month],
                    'Net Work Days': net_days,
                    'Office Days Required': office_days
                })
            # print('--------')
            # print(pd.DataFrame(monthly_data))
            display_metrics_and_charts(monthly_data, monthly_workdays, holidays)
        else:
            st.error("Total PTO exceeds allowance!")
            pass
        
