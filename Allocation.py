import streamlit as st
import pandas as pd
from collections import defaultdict

# Function to scrape data from an Excel sheet
def scrape_data_from_excel(file):
    df = pd.read_excel(file, engine='openpyxl')
    df = df[['DMX_ISSUER_ID', 'DMX_ISSUER_NAME', 'TOTAL', 'COUNTRY_DOMICILE', 'RUN_DATE']]
    return df

# Main allocation function based on run-date wise round-robin
def allocate_run_date_round_robin(df, team_members):
    team_totals = {member: 0 for member in team_members}
    member_dates = {member: set() for member in team_members}
    allocation = []
    allocated_issuers = set()

    # Group issuers by RUN_DATE
    grouped_by_date = df.groupby('RUN_DATE')

    for run_date, group in grouped_by_date:
        issuers = group.sort_values(by='TOTAL', ascending=False).to_dict(orient='records')
        member_index = 0

        for issuer in issuers:
            # Sort members by fewest run dates, then by total points
            sorted_members = sorted(
                team_members,
                key=lambda m: (len(member_dates[m]), team_totals[m])
            )

            # Pick member in round-robin style
            member = sorted_members[member_index % len(team_members)]
            member_index += 1

            allocation.append((
                issuer['DMX_ISSUER_ID'],
                issuer['DMX_ISSUER_NAME'],
                issuer['TOTAL'],
                issuer['COUNTRY_DOMICILE'],
                issuer['RUN_DATE'],
                member
            ))

            team_totals[member] += issuer['TOTAL']
            member_dates[member].add(issuer['RUN_DATE'])
            allocated_issuers.add(issuer['DMX_ISSUER_ID'])

    return allocation

# Full allocation logic
def allocate_issuers(df, team_members):
    us_issuers = df[df['COUNTRY_DOMICILE'] == 'US']
    non_us_issuers = df[df['COUNTRY_DOMICILE'] != 'US']

    allocation = []

    # Allocate US issuers
    us_allocation = allocate_run_date_round_robin(us_issuers, team_members)
    allocation.extend(us_allocation)

    # Recalculate running totals and run dates before next phase
    team_totals = defaultdict(int)
    member_dates = defaultdict(set)
    for _, _, total, _, run_date, member in us_allocation:
        team_totals[member] += total
        member_dates[member].add(run_date)

    # Allocate non-US issuers using the same logic
    grouped_by_date = non_us_issuers.groupby('RUN_DATE')
    for run_date, group in grouped_by_date:
        issuers = group.sort_values(by='TOTAL', ascending=False).to_dict(orient='records')
        member_index = 0

        for issuer in issuers:
            sorted_members = sorted(
                team_members,
                key=lambda m: (len(member_dates[m]), team_totals[m])
            )
            member = sorted_members[member_index % len(team_members)]
            member_index += 1

            allocation.append((
                issuer['DMX_ISSUER_ID'],
                issuer['DMX_ISSUER_NAME'],
                issuer['TOTAL'],
                issuer['COUNTRY_DOMICILE'],
                issuer['RUN_DATE'],
                member
            ))

            team_totals[member] += issuer['TOTAL']
            member_dates[member].add(run_date)

    # Final DataFrame
    allocation_df = pd.DataFrame(
        allocation,
        columns=['DMX_ISSUER_ID', 'DMX_ISSUER_NAME', 'TOTAL', 'COUNTRY_DOMICILE', 'RUN_DATE', 'Team_Member']
    )
    return allocation_df

# Validation function
def validate_allocation(allocation_df, team_members):
    total_points = allocation_df['TOTAL'].sum()
    average_points_per_member = total_points / len(team_members)
    validation_results = {}

    for member in team_members:
        member_total = allocation_df[allocation_df['Team_Member'] == member]['TOTAL'].sum()
        difference_from_average = member_total - average_points_per_member
        unique_dates = allocation_df[allocation_df['Team_Member'] == member]['RUN_DATE'].nunique()

        validation_results[member] = {
            'Total': member_total,
            'Difference from Average': difference_from_average,
            'Above Average': difference_from_average > 0,
            'Below Average': difference_from_average < 0,
            'Unique Dates Assigned': unique_dates
        }
    return validation_results, average_points_per_member

# Streamlit UI
st.title("Issuer Allocation System - Run Date Wise & Balanced")

uploaded_file = st.file_uploader("Upload Excel File", type=["xlsx"])
team_input = st.text_input("Enter Team Members (comma-separated):")
team_members = [name.strip() for name in team_input.split(',') if name.strip()]

if uploaded_file is not None and team_members:
    df = scrape_data_from_excel(uploaded_file)
    allocation_df = allocate_issuers(df, team_members)
    allocation_df = allocation_df.set_index('DMX_ISSUER_ID').reindex(df['DMX_ISSUER_ID']).reset_index()
    validation_results, avg_points = validate_allocation(allocation_df, team_members)

    st.subheader("Allocation Results")
    st.dataframe(allocation_df)

    st.subheader("Validation Results")
    st.write(f"**Average Points per Member:** {avg_points:.2f}")
    for member, result in validation_results.items():
        status = "Above Average" if result['Above Average'] else "Below Average"
        color = "green" if result['Above Average'] else "red"
        st.markdown(
            f"**{member}**: Total - {result['Total']}, "
            f"Dates Assigned - {result['Unique Dates Assigned']}, "
            f"Difference from Average - :{color}[{result['Difference from Average']:.2f}] ({status})"
        )

    st.download_button(
        label="Download Allocation Result",
        data=allocation_df.to_csv(index=False).encode('utf-8'),
        file_name='allocation_results.csv',
        mime='text/csv'
    )
