import asyncio
import streamlit as st
import holidays as hd
import math
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import plotly.express as px
from pandas.tseries.holiday import USFederalHolidayCalendar
from openai import OpenAI
import os
from math_tool import calculator_tool

databricks_key = st.secrets['general']["DATABRICKS_API_KEY"]
openai_key = st.secrets['general']["OPENAI_API_KEY"]

def get_custom_holidays(start_date, end_date, extended_christmas_break):
    start = pd.to_datetime(start_date)
    end = pd.to_datetime(end_date)

    # Initialize US holidays
    us_holidays = hd.US(years=range(start_date.year, end_date.year + 1))

    # Get federal holidays from the `holidays` module
    federal_holidays = {date: name for date, name in us_holidays.items() if start <= pd.to_datetime(date) <= end}

    # Compute additional holidays
    additional_holidays = {}

    year = start_date.year
    thanksgiving = pd.to_datetime(pd.date_range(start=f"{year}-11-01", end=f"{year}-11-30", freq="W-THU")[3])
   
    if start <= thanksgiving <= end:
        day_after_thanksgiving = thanksgiving + timedelta(days=1)
        additional_holidays[day_after_thanksgiving] = "Day After Thanksgiving"

    # Add Christmas Break (Dec 24–Dec 31, skipping weekends)
    if extended_christmas_break:
        christmas_break = pd.date_range(start=f"{year}-12-24", end=f"{year}-12-31")
        christmas_break = christmas_break[~christmas_break.weekday.isin([5, 6])]

        for date in christmas_break:
            if start <= date <= end:
                additional_holidays[date] = "Christmas Break"

    # Merge all holidays
    all_holidays = {**federal_holidays, **additional_holidays}

    # Convert to DataFrame
    holiday_df = pd.DataFrame(list(all_holidays.items()), columns=["Date", "Holiday Name"])
    holiday_df["Date"] = pd.to_datetime(holiday_df["Date"])

    holiday_df_sorted = holiday_df.sort_values("Date").reset_index(drop=True)

    holiday_result_dict = {
        'holiday_df': holiday_df,
        'holiday_dates': holiday_df["Date"]
    }
    return holiday_result_dict

def calculate_workdays(start_date, end_date):
    """Calculate number of workdays between two dates, excluding US federal holidays."""
    holidays = get_custom_holidays(start_date, end_date, extended_christmas_break)['holiday_dates']
    
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
    
    with st.container(border = True):
        st.subheader("✨ Use AI to help for PTO Planning ✨")
        st.write("AI can make mistake, use the feature carefully and verify the result.")
        ai_pto_factor = st.radio("Do you want AI to factor in PTO you have already planned (entered)?", 
                ["Yes, and plan additional PTOs", "No, help me plan from scratch"],
                key="ai_pto_factor")
        if st.session_state.ai_pto_factor == "No, help me plan from scratch":
            ai_pto_days=st.number_input(
                'How many PTOs total do you want to take?',
                min_value=0.0,
                max_value=60.0,
                value=3.0,
                step = 0.5, 
                key="ai_pto_days"
            )
            monthly_data = []
            for month, workdays in monthly_workdays.items():
                if st.session_state.pto_accounting_policy == 'PTO subtracted from workdays':
                    net_days = workdays
                    office_days = round(net_days * 0.6, 0)
                else:
                    net_days = workdays
                    office_days = round(net_days * 0.6, 0)
                monthly_data.append({
                    'Month': pd.to_datetime(month + "-01").strftime("%b %Y"),
                    'Work Days': workdays,
                    'PTO Days': 0,
                    'Net Work Days': net_days,
                    'Office Days Required': office_days
                })
            print(pd.DataFrame(monthly_data))
            
        st.text_input(label="What other criteria do you want AI to consider?",
                    placeholder='eg. I want to take 2 weeks off in July',
                    key="ai_pto_additional_criteria")
        
        additional_info =f"""
        Here is the additional info to consider:

        Total PTO I want to take: {st.session_state.ai_pto_days}

        Additional criteria: {st.session_state.ai_pto_additional_criteria}
        """
        pto_allowance=st.session_state.pto_allowance
        office_day_formula = required_office_days_formula(st.session_state.pto_accounting_policy)
        show_ai_button(monthly_data, monthly_workdays, holidays, additional_info, pto_allowance, office_day_formula)

def show_ai_button(monthly_data, monthly_workdays, holidays, additional_info=None, pto_allowance=None, office_day_formula=None):
    if st.button("🪄AI Suggest PTO Plan", type='primary'):
        with st.spinner("Thinking...feel free to grab a beverage while you wait"):
            prompt = f"""
            Use the monthly data and holidays to help me optimize my PTO plan.
            I have a total {pto_allowance} number of PTO days to take in this period.

            Focus on which month I should take PTO to minimize the total office days required.
            Factor in weekends and company holidays to maximize day offs.
            Do not suggest day offs between Christmas and New year since this is already a company holiday.
            Also avoid suggesting taking day off for a whole week if I need to take Monday to Friday off using PTOs.

            Here is the monthly data of how many work days, holidays, PTO days and office days required for each month:
            {monthly_data}\n

            Here are the company holidays during this period:
            {holidays}\n

            Here are additional criteria I want you to consider:
            {additional_info}\n

            Use this formula and calculator tool to calculate the required office days:\n
            {office_day_formula}

            Use this format for your suggestions:\n
            **Overall summary**: \n
            [summary of the strategy]

            PTO strategy by month:
            - Month: [Month]
             - PTO Days: [Number of PTO Days]
             - Total required office days: [Number of days to go into office subtracting the suggested PTO and holidays]
             - Dates to take: [Dates to take PTO to maximize day offs including weekends and holidays]
            """
            output = asyncio.run(calculator_tool(prompt))
            formatted_output = output[-1].content
        
        st.markdown(f"**AI Suggested PTO Plan**:\n {formatted_output}")        

def reset_global_var():
    st.session_state.monthly_data = None
    st.session_state.monthly_workdays = None
    st.session_state.total_pto = 0

def required_office_days_formula(pto_accounting_policy):
    if pto_accounting_policy == 'PTO subtracted from workdays':
        formula = """
        The formula of required office day is: [(Number of workday - PTO days) * 0.6]

        For example, if there are 22 work days, and I take 10 PTO, then required office day is (22-10)*0.6 = 7.2 days
        """
    else:
        formula = """
        The formula of required office day is: [Number of workday * 0.6 - PTO days] \n
        For example, if there are 22 work days, and I take 10 PTO, then required office day is 22*0.6 - 10  = 3.2 days
        """
    return formula

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
        st.session_state.pto_accounting_policy = 'PTO subtracted from workdays'
    if 'ai_pto_factor' not in st.session_state:
        st.session_state.ai_pto_factor = 'Yes, and plan additional PTOs'
    if 'ai_pto_days' not in st.session_state:
        st.session_state.ai_pto_days = 0


#####START OF THE APP ########
init_session_state() # Initialize session state variables

st.title("Return to Office Calculator")
st.write("Calculate your required office days based on the RTO policy")

#Side bar expanders for PTO inputs
with st.sidebar:
    st.title("Start here!")
    # Date range selection
    with st.container():
        st.subheader("Date Range for RTO calculation")
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input("Start Date", datetime(datetime.today().year, 1, 1))
        with col2:
            end_date = st.date_input("End Date", datetime(datetime.today().year, 12, 31))
        st.checkbox("Holiday between Christmas and New Year?", value=True,key="extended_christmas_break")
        extended_christmas_break = st.session_state.extended_christmas_break
    
    with st.container(border = True):
        st.subheader("RTO policy")
        st.number_input(
            "% of workdays required in office",
            min_value=0.0,
            max_value=100.0,
            value=60.0,
            step=1.0,
            key="workdays_percentage",
            help="Enter the percentage of workdays you are required to be in office"
        )


    st.subheader("PTO Planning")
    with st.expander("PTO days you have in this period", expanded = True):
        total_pto_allowance = st.number_input(
                                    "PTO allowance",
                                    min_value=0.0,
                                    max_value=60.0,
                                    value=20.0,
                                    step=0.5,
                                    key="pto_allowance",
                                    help="Enter total PTO allowance for the period, this may include carry-over PTO days"
                                )
    
    with st.expander("PTO accounting policy", expanded = True):
        pto_accounting_policy = st.radio(
            'Choose how PTO is accounted for', 
            ['PTO subtracted from workdays', 'PTO as a day in office'],
            horizontal=True,
            key='pto_accounting_policy', 
            help="""
            PTO subtracted from work days means the total number of work days are reduced by number of PTO you take. 
            PTO as a day in office means total number of work day is not impacted, but a PTO is considered as a day in office.
            """
        )
        if st.session_state.pto_accounting_policy != pto_accounting_policy:
            st.session_state.pto_accounting_policy = pto_accounting_policy

    with st.expander("Choose how you want to plan your PTO days", expanded = True):
        tab = st.radio(
                        "Choose an option:",
                        ["Option1: Avg PTO per month", "Option2: PTO for each month"],
                        horizontal=True,
                        key="pto_selector", 
                        index = 0, 
                        help="""Choose how you want to plan your PTO days. First option is a quick way to see PTO impact 
                        if you have an idea of the average number of PTO you take a month.
                        If you have specific PTO days for individual month, choose the second option.
                        """
                )
        if st.session_state.tab != tab:
            st.session_state.tab = tab
#Tabs for PTO app & Company holiday views

app_tab, holiday_tab = st.tabs(["PTO Planner", "Company Holidays"])

with app_tab:
    #Option 1: use average PTO days per month
    if st.session_state.tab == "Option1: Avg PTO per month":
        reset_global_var()
        with st.container(border = True):
            monthly_pto = st.slider("Select average PTO days taken per month", 
                                    min_value=0.0, 
                                    max_value=7.0, 
                                    value=0.0,
                                    step=0.5,
                                    help="Select average number of PTO days you plan to take per month")
            #Get number of holidays
            holidays = get_custom_holidays(start_date, end_date, extended_christmas_break)['holiday_dates']

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
                if st.session_state.pto_accounting_policy == 'PTO subtracted from workdays':
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
            display_metrics_and_charts(monthly_data, monthly_workdays, holidays)
        else:
            st.error("Total PTO exceeds allowance!")
            pass

    #option 2: PTO for each month
    elif st.session_state.tab == "Option2: PTO for each month":
        reset_global_var()
        if start_date and end_date and start_date <= end_date:
            #Get number of holidays
            holidays = get_custom_holidays(start_date, end_date, extended_christmas_break)['holiday_dates']
            # Calculate monthly workdays
            monthly_workdays = calculate_monthly_workdays(start_date, end_date)
            # Create columns for PTO inputs
            with st.container(border = True):
                st.write('Enter PTO days for each month')
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
                    if st.session_state.pto_accounting_policy == 'PTO subtracted from workdays':
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
                display_metrics_and_charts(monthly_data, monthly_workdays, holidays)
            else:
                st.error("Total PTO exceeds allowance!")
                pass

with holiday_tab:
    st.subheader("Company Holidays")
    holidays_df = get_custom_holidays(start_date, end_date, extended_christmas_break)['holiday_df']
    holidays_df['Date'] = holidays_df['Date'].dt.strftime('%b %d, %Y')
    st.dataframe(holidays_df, hide_index=True, use_container_width=True)