import streamlit as st
import pandas as pd

# Function to scrape data from an Excel sheet
def scrape_data_from_excel(file):
    df = pd.read_excel(file, engine='openpyxl')
    df = df[['DMX_ISSUER_ID', 'DMX_ISSUER_NAME', 'TOTAL', 'COUNTRY_DOMICILE', 'RUN_DATE']]
    return df

# Function to allocate issuers to team members with date constraints
def allocate_issuers(df, team_members):
    team_totals = {member: 0 for member in team_members}
    member_dates = {member: set() for member in team_members}
    allocation = []
    allocated_issuers = set()

    level_1_countries = ['AU', 'CA', 'GB', 'HK', 'IE', 'MY', 'NZ', 'SG']
    level_2_countries = ['AE', 'AR', 'AT', 'AZ', 'BE', 'BF', 'BG', 'BH', 'BM', 'BS', 'CH', 'CL', 'CO', 'CR', 'CY', 'CZ',
                         'DE', 'DK', 'EE', 'ES', 'FI', 'FO', 'FR', 'GE', 'GG', 'GI', 'GR', 'HR', 'HU', 'ID', 'IL',
                         'IM', 'IN', 'JE', 'KE', 'KW', 'KY', 'KZ', 'LI', 'LT', 'LU', 'MA', 'MC', 'MN', 'MO',
                         'MT', 'MU', 'MX', 'NG', 'NL', 'NO', 'OM', 'PA', 'PE', 'PH', 'PK', 'PL', 'PR', 'PT', 'QA', 'RO',
                         'SA', 'SE', 'SK', 'SN', 'SV', 'TG', 'TH', 'TN', 'UA', 'UY', 'VG', 'PG', 'CI']
    level_3_countries = ['BR', 'CN', 'EG', 'IT', 'RU', 'TR', 'TW', 'ZA', 'IS']

    # Assign priority levels
    def assign_level(country):
        if country == 'US':
            return 0
        elif country in level_1_countries:
            return 1
        elif country in level_2_countries:
            return 2
        elif country in level_3_countries:
            return 3
        else:
            return 4

    df['LEVEL'] = df['COUNTRY_DOMICILE'].apply(assign_level)

    # Sort for consistent processing: by LEVEL, then by DATE_TAGGED
    df = df.sort_values(by=['LEVEL', 'RUN_DATE'])

    # Group issuers by date
    grouped_by_date = dict(tuple(df.groupby('RUN_DATE')))

    for date, group in grouped_by_date.items():
        for index, row in group.iterrows():
            if row['DMX_ISSUER_ID'] in allocated_issuers:
                continue

            # Filter members who can take this date
           eligible_members = [m for m in team_members if len(member_dates[m]) < 3 or date in member_dates[m]]

# Fallback if no one qualifies under the date limit
if not eligible_members:
    eligible_members = team_members  # allow breaking the "max 3 dates" rule

chosen = min(eligible_members, key=lambda x: team_totals[x])

            # Pick the one with lowest total
            chosen = min(eligible_members, key=lambda x: team_totals[x])

            allocation.append((
                row['DMX_ISSUER_ID'],
                row['DMX_ISSUER_NAME'],
                row['TOTAL'],
                row['COUNTRY_DOMICILE'],
                row['RUN_DATE'],
                chosen
            ))

            team_totals[chosen] += row['TOTAL']
            member_dates[chosen].add(date)
            allocated_issuers.add(row['DMX_ISSUER_ID'])

    allocation_df = pd.DataFrame(
        allocation,
        columns=['DMX_ISSUER_ID', 'DMX_ISSUER_NAME', 'TOTAL', 'COUNTRY_DOMICILE', 'RUN_DATE', 'Team_Member']
    )
    return allocation_df

# Function to validate the allocation
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

# Streamlit Interface
st.title("Issuer Allocation System with Date Constraint")

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
