import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO
import base64
import datetime

# Configure the page
st.set_page_config(
    page_title="LLB Rank List Generator",
    page_icon="📚",
    layout="wide"
)

# Define section mapping
SECTION_MAPPING = {
    'English': list(range(1, 37)),
    'General Knowledge': list(range(37, 64)),
    'Arithmetic & Mental Ability': list(range(64, 79)),
    'Aptitude for Legal Studies': list(range(79, 121))
}

# Define section total questions
SECTION_TOTALS = {
    'English': 36,
    'General Knowledge': 27,
    'Arithmetic & Mental Ability': 15,
    'Aptitude for Legal Studies': 42
}

def determine_section(qno):
    """Determine which section a question belongs to based on question number"""
    if 1 <= qno <= 36:
        return 'English'
    elif 37 <= qno <= 63:
        return 'General Knowledge'
    elif 64 <= qno <= 78:
        return 'Arithmetic & Mental Ability'
    elif 79 <= qno <= 120:
        return 'Aptitude for Legal Studies'
    return None

def safe_convert_dob(dob_value):
    """Safely convert DOB to datetime, handling various formats and null values"""
    if pd.isna(dob_value) or dob_value == '0000-00-00' or dob_value == '':
        return pd.NaT
    
    try:
        # If it's already a datetime object
        if isinstance(dob_value, (pd.Timestamp, datetime.datetime)):
            return dob_value
        
        # If it's a string
        if isinstance(dob_value, str):
            # Try different formats
            formats = ['%Y-%m-%d', '%d-%m-%Y', '%m/%d/%Y', '%d/%m/%Y']
            for fmt in formats:
                try:
                    return pd.to_datetime(dob_value, format=fmt)
                except:
                    continue
            
            # Try pandas flexible parsing
            try:
                return pd.to_datetime(dob_value)
            except:
                return pd.NaT
        
        # If it's a number (timestamp)
        if isinstance(dob_value, (int, float)):
            try:
                return pd.to_datetime(dob_value, unit='D', origin='1899-12-30')
            except:
                return pd.NaT
                
        return pd.NaT
    except:
        return pd.NaT

def calculate_section_marks(df, deleted_questions):
    """Calculate marks section-wise with correction factor"""
    section_marks = {}
    section_raw_marks = {}
    section_stats = {}
    
    # Initialize dictionaries
    for section in SECTION_TOTALS.keys():
        section_marks[section] = 0
        section_raw_marks[section] = {'obtained': 0, 'attempted': 0, 'correct': 0, 'incorrect': 0, 'unattempted': 0}
        section_stats[section] = {'correct': 0, 'wrong': 0, 'unattempted': 0}
    
    # Group by section and calculate
    for _, row in df.iterrows():
        try:
            qno = int(row['QNo'])
            mark = float(row['Mark']) if pd.notna(row['Mark']) else 0
            section = determine_section(qno)
            
            if section is None:
                continue
                
            # Check if question is deleted
            if qno in deleted_questions.get(section, []):
                continue
                
            # Count attempts and marks
            if mark == 3:
                section_raw_marks[section]['correct'] += 1
                section_raw_marks[section]['attempted'] += 1
                section_stats[section]['correct'] += 1
            elif mark == -1:
                section_raw_marks[section]['incorrect'] += 1
                section_raw_marks[section]['attempted'] += 1
                section_stats[section]['wrong'] += 1
            elif mark == 0:
                section_stats[section]['unattempted'] += 1
            
            section_raw_marks[section]['obtained'] += mark
        except Exception as e:
            # Skip problematic rows
            continue
    
    # Calculate unattempted counts for each section
    for section in SECTION_TOTALS.keys():
        total_questions = SECTION_TOTALS[section]
        deleted_count = len(deleted_questions.get(section, []))
        remaining_questions = total_questions - deleted_count
        attempted = section_raw_marks[section]['correct'] + section_raw_marks[section]['incorrect']
        unattempted = remaining_questions - attempted
        section_stats[section]['unattempted'] = unattempted
    
    # Apply correction factor
    for section, totals in section_raw_marks.items():
        total_questions = SECTION_TOTALS[section]
        deleted_count = len(deleted_questions.get(section, []))
        remaining_questions = total_questions - deleted_count
        
        if remaining_questions > 0:
            obtained_marks = totals['obtained']
            # Formula: (Obtained Marks / Remaining Questions) * Total Questions
            corrected_marks = (obtained_marks / remaining_questions) * total_questions
            section_marks[section] = round(corrected_marks, 4)
        else:
            section_marks[section] = 0
    
    return section_marks, section_raw_marks, section_stats

def apply_qualification(total_marks, category):
    """Check if candidate qualifies based on category"""
    total_possible_marks = 360  # 120 questions * 3 marks
    
    # Handle None or null category
    if pd.isna(category) or category is None:
        category = 'General'
    
    category = str(category).strip()
    
    if category in ['SC', 'ST']:
        min_percentage = 5
    else:
        min_percentage = 10
    
    min_marks = (min_percentage / 100) * total_possible_marks
    return total_marks >= min_marks

def resolve_tie(candidates_df):
    """Apply tie-breaking rules"""
    if candidates_df.empty:
        return candidates_df
    
    # Create a copy to avoid modifying original
    df = candidates_df.copy()
    
    # Sort by total marks descending
    df = df.sort_values(['Total_Marks'], ascending=[False])
    
    # Create rank column
    df['Rank'] = range(1, len(df) + 1)
    
    # Handle ties
    i = 0
    while i < len(df):
        j = i + 1
        # Find all candidates with same total marks
        while j < len(df) and df.iloc[i]['Total_Marks'] == df.iloc[j]['Total_Marks']:
            j += 1
        
        if j - i > 1:  # There's a tie
            # Sort tie group by Aptitude for Legal Studies
            tie_group = df.iloc[i:j].copy()
            tie_group = tie_group.sort_values(['Aptitude_for_Legal_Studies'], ascending=[False])
            
            # Check if tie persists
            k = 0
            while k < len(tie_group):
                l = k + 1
                while l < len(tie_group) and tie_group.iloc[k]['Aptitude_for_Legal_Studies'] == tie_group.iloc[l]['Aptitude_for_Legal_Studies']:
                    l += 1
                
                if l - k > 1:  # Tie persists
                    # Sort by English marks
                    sub_tie_group = tie_group.iloc[k:l].copy()
                    sub_tie_group = sub_tie_group.sort_values(['English'], ascending=[False])
                    
                    # Check if tie persists further
                    m = 0
                    while m < len(sub_tie_group):
                        n = m + 1
                        while n < len(sub_tie_group) and sub_tie_group.iloc[m]['English'] == sub_tie_group.iloc[n]['English']:
                            n += 1
                        
                        if n - m > 1:  # Tie persists
                            # Sort by Arithmetic & Mental Ability
                            sub_sub_tie_group = sub_tie_group.iloc[m:n].copy()
                            sub_sub_tie_group = sub_sub_tie_group.sort_values(['Arithmetic_and_Mental_Ability'], ascending=[False])
                            
                            # Check if tie persists further
                            o = 0
                            while o < len(sub_sub_tie_group):
                                p = o + 1
                                while p < len(sub_sub_tie_group) and sub_sub_tie_group.iloc[o]['Arithmetic_and_Mental_Ability'] == sub_sub_tie_group.iloc[p]['Arithmetic_and_Mental_Ability']:
                                    p += 1
                                
                                if p - o > 1:  # Tie persists
                                    # Sort by age (elder first)
                                    age_group = sub_sub_tie_group.iloc[o:p].copy()
                                    # Convert DOB to datetime safely
                                    age_group['DOB_clean'] = age_group['DOB'].apply(safe_convert_dob)
                                    # Sort by DOB (older first, meaning earlier dates)
                                    age_group = age_group.sort_values(['DOB_clean'], ascending=[True])
                                    # Drop the temporary column
                                    age_group = age_group.drop('DOB_clean', axis=1)
                                    sub_sub_tie_group.iloc[o:p] = age_group
                                
                                o = p
                            
                            sub_tie_group.iloc[m:n] = sub_sub_tie_group
                        
                        m = n
                    
                    tie_group.iloc[k:l] = sub_tie_group
                
                k = l
            
            df.iloc[i:j] = tie_group
        
        i = j
    
    # Reassign ranks after tie-breaking
    df['Rank'] = range(1, len(df) + 1)
    
    return df

def generate_rank_list(candidates_df, responses_df, deleted_questions, apply_qual=False):
    """Generate the complete rank list"""
    try:
        # Ensure required columns exist
        required_candidate_cols = ['ApplNo', 'RollNo']
        required_response_cols = ['ApplNo', 'RollNo', 'QNo', 'Mark']
        
        # Check if required columns exist
        for col in required_candidate_cols:
            if col not in candidates_df.columns:
                st.error(f"Required column '{col}' not found in candidates file")
                return pd.DataFrame()
        
        for col in required_response_cols:
            if col not in responses_df.columns:
                st.error(f"Required column '{col}' not found in responses file")
                return pd.DataFrame()
        
        # Merge candidate data with responses
        merged_df = candidates_df.merge(responses_df, on=['ApplNo', 'RollNo'], how='inner')
        
        if merged_df.empty:
            st.warning("No matching records found between candidates and responses")
            return pd.DataFrame()
        
        # Calculate section-wise marks for each candidate
        results = []
        
        for (applno, rollno), group in merged_df.groupby(['ApplNo', 'RollNo']):
            try:
                # Get candidate details
                candidate_rows = candidates_df[
                    (candidates_df['ApplNo'] == applno) & 
                    (candidates_df['RollNo'] == rollno)
                ]
                
                if candidate_rows.empty:
                    continue
                
                candidate_info = candidate_rows.iloc[0]
                
                # Calculate section marks
                section_marks, raw_marks, section_stats = calculate_section_marks(group, deleted_questions)
                
                # Calculate total marks
                total_marks = sum(section_marks.values())
                
                # Get category safely
                category = candidate_info.get('Category', 'General')
                if pd.isna(category):
                    category = 'General'
                
                # Check qualification
                qualifies = apply_qualification(total_marks, category) if apply_qual else True
                
                # Get DOB safely
                dob = candidate_info.get('DOB', 'N/A')
                if pd.isna(dob) or dob == '0000-00-00':
                    dob = 'N/A'
                else:
                    try:
                        dob_clean = safe_convert_dob(dob)
                        if pd.notna(dob_clean):
                            dob = dob_clean.strftime('%Y-%m-%d')
                        else:
                            dob = str(dob)
                    except:
                        dob = str(dob)
                
                result = {
                    'ApplNo': applno,
                    'RollNo': rollno,
                    'Name': str(candidate_info.get('Name', 'N/A')),
                    'DOB': dob,
                    'Category': str(category),
                    'Community': str(candidate_info.get('Community', 'N/A')),
                    
                    # Section marks (corrected)
                    'English_Marks': section_marks.get('English', 0),
                    'GK_Marks': section_marks.get('General Knowledge', 0),
                    'Arithmetic_Marks': section_marks.get('Arithmetic & Mental Ability', 0),
                    'Legal_Marks': section_marks.get('Aptitude for Legal Studies', 0),
                    
                    # Section-wise correct/wrong/unattempted counts
                    'Eng_Correct': section_stats.get('English', {}).get('correct', 0),
                    'Eng_Wrong': section_stats.get('English', {}).get('wrong', 0),
                    'Eng_Unattempted': section_stats.get('English', {}).get('unattempted', 0),
                    
                    'GK_Correct': section_stats.get('General Knowledge', {}).get('correct', 0),
                    'GK_Wrong': section_stats.get('General Knowledge', {}).get('wrong', 0),
                    'GK_Unattempted': section_stats.get('General Knowledge', {}).get('unattempted', 0),
                    
                    'Arith_Correct': section_stats.get('Arithmetic & Mental Ability', {}).get('correct', 0),
                    'Arith_Wrong': section_stats.get('Arithmetic & Mental Ability', {}).get('wrong', 0),
                    'Arith_Unattempted': section_stats.get('Arithmetic & Mental Ability', {}).get('unattempted', 0),
                    
                    'Legal_Correct': section_stats.get('Aptitude for Legal Studies', {}).get('correct', 0),
                    'Legal_Wrong': section_stats.get('Aptitude for Legal Studies', {}).get('wrong', 0),
                    'Legal_Unattempted': section_stats.get('Aptitude for Legal Studies', {}).get('unattempted', 0),
                    
                    # Total response statistics
                    'Total_Correct': sum([section_stats.get(s, {}).get('correct', 0) for s in SECTION_TOTALS.keys()]),
                    'Total_Wrong': sum([section_stats.get(s, {}).get('wrong', 0) for s in SECTION_TOTALS.keys()]),
                    'Total_Unattempted': sum([section_stats.get(s, {}).get('unattempted', 0) for s in SECTION_TOTALS.keys()]),
                    
                    'Total_Marks': total_marks,
                    'Qualifies': qualifies
                }
                results.append(result)
            except Exception as e:
                st.warning(f"Error processing candidate {rollno}: {str(e)}")
                continue
        
        if not results:
            st.warning("No results could be calculated")
            return pd.DataFrame()
        
        # Create DataFrame
        result_df = pd.DataFrame(results)
        
        # Filter qualified candidates if needed
        if apply_qual:
            result_df = result_df[result_df['Qualifies'] == True]
        
        # Apply tie-breaking
        if not result_df.empty:
            result_df = resolve_tie(result_df)
        else:
            result_df['Rank'] = []
        
        return result_df.sort_values('Rank')
        
    except Exception as e:
        st.error(f"Error generating rank list: {str(e)}")
        import traceback
        st.error(traceback.format_exc())
        return pd.DataFrame()

def get_excel_download_link(df, filename="rank_list.xlsx"):
    """Generate download link for Excel file"""
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Rank List')
    
    excel_data = output.getvalue()
    b64 = base64.b64encode(excel_data).decode()
    href = f'<a href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{b64}" download="{filename}">Download Excel File</a>'
    return href

def main():
    st.title("📚 LLB Rank List Generator")
    st.markdown("---")
    
    # File uploads
    col1, col2 = st.columns(2)
    
    with col1:
        candidates_file = st.file_uploader(
            "Upload Candidates File",
            type=['csv', 'xlsx', 'xls'],
            help="Upload file containing candidate information"
        )
    
    with col2:
        responses_file = st.file_uploader(
            "Upload CBT Responses File",
            type=['csv', 'xlsx', 'xls'],
            help="Upload file containing CBT responses with marks"
        )
    
    if candidates_file and responses_file:
        try:
            # Read files with error handling
            try:
                if candidates_file.name.endswith('.csv'):
                    candidates_df = pd.read_csv(candidates_file)
                else:
                    candidates_df = pd.read_excel(candidates_file)
            except Exception as e:
                st.error(f"Error reading candidates file: {str(e)}")
                st.stop()
            
            try:
                if responses_file.name.endswith('.csv'):
                    responses_df = pd.read_csv(responses_file)
                else:
                    responses_df = pd.read_excel(responses_file)
            except Exception as e:
                st.error(f"Error reading responses file: {str(e)}")
                st.stop()
            
            st.success("✅ Files uploaded successfully!")
            
            # Clean and prepare data
            # Ensure numeric columns are properly typed
            for col in ['ApplNo', 'RollNo']:
                if col in candidates_df.columns:
                    candidates_df[col] = candidates_df[col].astype(str)
                if col in responses_df.columns:
                    responses_df[col] = responses_df[col].astype(str)
            
            if 'QNo' in responses_df.columns:
                responses_df['QNo'] = pd.to_numeric(responses_df['QNo'], errors='coerce')
            
            if 'Mark' in responses_df.columns:
                responses_df['Mark'] = pd.to_numeric(responses_df['Mark'], errors='coerce').fillna(0)
            
            # Show preview
            with st.expander("Preview Candidates Data"):
                st.dataframe(candidates_df.head())
            
            with st.expander("Preview CBT Responses Data"):
                st.dataframe(responses_df.head())
            
            st.markdown("---")
            
            # Correction Factor Section
            st.subheader("📊 Correction Factor for Deleted Questions")
            
            deleted_questions = {}
            
            col1, col2 = st.columns(2)
            
            with col1:
                english_deleted = st.text_input(
                    "English Deleted Questions (comma-separated)",
                    placeholder="e.g., 22,25"
                )
                if english_deleted:
                    deleted_questions['English'] = [int(x.strip()) for x in english_deleted.split(',') if x.strip().isdigit()]
                else:
                    deleted_questions['English'] = []
                
                gk_deleted = st.text_input(
                    "General Knowledge Deleted Questions (comma-separated)",
                    placeholder="e.g., 42,48"
                )
                if gk_deleted:
                    deleted_questions['General Knowledge'] = [int(x.strip()) for x in gk_deleted.split(',') if x.strip().isdigit()]
                else:
                    deleted_questions['General Knowledge'] = []
            
            with col2:
                arithmetic_deleted = st.text_input(
                    "Arithmetic Deleted Questions (comma-separated)",
                    placeholder="e.g., 70,75"
                )
                if arithmetic_deleted:
                    deleted_questions['Arithmetic & Mental Ability'] = [int(x.strip()) for x in arithmetic_deleted.split(',') if x.strip().isdigit()]
                else:
                    deleted_questions['Arithmetic & Mental Ability'] = []
                
                legal_deleted = st.text_input(
                    "Legal Deleted Questions (comma-separated)",
                    placeholder="e.g., 90,105"
                )
                if legal_deleted:
                    deleted_questions['Aptitude for Legal Studies'] = [int(x.strip()) for x in legal_deleted.split(',') if x.strip().isdigit()]
                else:
                    deleted_questions['Aptitude for Legal Studies'] = []
            
            st.markdown("---")
            
            # Qualification Criteria
            apply_qual = st.checkbox(
                "✅ Apply Qualification Criteria",
                help="Apply minimum marks criteria based on category"
            )
            
            if apply_qual:
                st.info("""
                **Qualification Criteria:**
                - General/SEBC: Minimum 10% of total marks (36 marks out of 360)
                - SC/ST: Minimum 5% of total marks (18 marks out of 360)
                """)
            
            st.markdown("---")
            
            # Generate Rank List Button
            if st.button("🎯 Generate Rank List", type="primary"):
                with st.spinner("Generating rank list..."):
                    result_df = generate_rank_list(
                        candidates_df, 
                        responses_df, 
                        deleted_questions,
                        apply_qual
                    )
                    
                    if not result_df.empty:
                        st.success("✅ Rank list generated successfully!")
                        
                        # Display summary statistics
                        st.subheader("📊 Summary Statistics")
                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            st.metric("Total Candidates", len(result_df))
                        with col2:
                            if not result_df.empty:
                                st.metric("Highest Score", f"{result_df['Total_Marks'].max():.2f}")
                        with col3:
                            if not result_df.empty:
                                st.metric("Average Score", f"{result_df['Total_Marks'].mean():.2f}")
                        with col4:
                            if not result_df.empty:
                                st.metric("Total Correct Responses", f"{result_df['Total_Correct'].sum():.0f}")
                        
                        # Display top 10
                        st.subheader("🏆 Top 10 Rank List")
                        st.dataframe(
                            result_df[['Rank', 'RollNo', 'Name', 'Total_Marks', 
                                     'English_Marks', 'GK_Marks', 
                                     'Arithmetic_Marks', 'Legal_Marks']].head(10),
                            use_container_width=True
                        )
                        
                        # Display full rank list
                        with st.expander("📋 View Full Rank List"):
                            st.dataframe(
                                result_df[['Rank', 'ApplNo', 'RollNo', 'Name', 'DOB', 
                                         'Category', 'Total_Marks', 'Total_Correct', 'Total_Wrong', 'Total_Unattempted',
                                         'English_Marks', 'GK_Marks', 'Arithmetic_Marks', 'Legal_Marks']],
                                use_container_width=True
                            )
                        
                        # Download button
                        st.markdown("---")
                        st.markdown("### 📥 Download Rank List")
                        
                        # Format for download - includes all detailed statistics
                        download_df = result_df[['Rank', 'ApplNo', 'RollNo', 'Name', 'DOB', 
                                               'Category', 'Community',
                                               
                                               # Total statistics
                                               'Total_Marks', 'Total_Correct', 'Total_Wrong', 'Total_Unattempted',
                                               
                                               # Section marks
                                               'English_Marks', 'GK_Marks', 'Arithmetic_Marks', 'Legal_Marks',
                                               
                                               # English section statistics
                                               'Eng_Correct', 'Eng_Wrong', 'Eng_Unattempted',
                                               
                                               # GK section statistics
                                               'GK_Correct', 'GK_Wrong', 'GK_Unattempted',
                                               
                                               # Arithmetic section statistics
                                               'Arith_Correct', 'Arith_Wrong', 'Arith_Unattempted',
                                               
                                               # Legal section statistics
                                               'Legal_Correct', 'Legal_Wrong', 'Legal_Unattempted']]
                        
                        # Clean download data
                        download_df = download_df.fillna('N/A')
                        
                        # Rename columns for better readability
                        download_df.columns = ['Rank', 'ApplNo', 'RollNo', 'Name', 'DOB', 
                                              'Category', 'Community',
                                              'Total Marks', 'Total Correct', 'Total Wrong', 'Total Unattempted',
                                              'English Marks', 'GK Marks', 'Arithmetic Marks', 'Legal Marks',
                                              'Eng Correct', 'Eng Wrong', 'Eng Unattempted',
                                              'GK Correct', 'GK Wrong', 'GK Unattempted',
                                              'Arith Correct', 'Arith Wrong', 'Arith Unattempted',
                                              'Legal Correct', 'Legal Wrong', 'Legal Unattempted']
                        
                        download_link = get_excel_download_link(download_df)
                        st.markdown(download_link, unsafe_allow_html=True)
                        
                        # CSV download as alternative
                        csv = download_df.to_csv(index=False)
                        st.download_button(
                            label="Download CSV",
                            data=csv,
                            file_name="rank_list.csv",
                            mime="text/csv"
                        )
                        
                    else:
                        st.warning("No candidates qualified based on the criteria or no data available.")
            
        except Exception as e:
            st.error(f"❌ Error processing files: {str(e)}")
            st.error("Please make sure the files are in the correct format.")
            import traceback
            st.error(traceback.format_exc())
    
    else:
        st.info("👆 Please upload both Candidate and CBT Responses files to begin.")
        
        # Show expected format
        with st.expander("📋 Expected File Formats"):
            st.markdown("""
            ### Candidates File
            Should contain columns like:
            - `ApplNo`
            - `RollNo`
            - `Name`
            - `DOB` (Date of Birth - various formats accepted)
            - `Category` (General, SC, ST, etc.)
            - `Community`
            
            ### CBT Responses File
            Should contain columns like:
            - `ApplNo`
            - `RollNo`
            - `QNo` (Question Number: 1-120)
            - `Ans` (Selected Answer)
            - `Mark` (3 for correct, 0 for unanswered, -1 for incorrect)
            
            ### Question Distribution
            - **English**: Questions 1-36
            - **General Knowledge**: Questions 37-63
            - **Arithmetic & Mental Ability**: Questions 64-78
            - **Aptitude for Legal Studies**: Questions 79-120
            
            ### Output Columns
            The generated Excel file will include:
            - **Basic Info**: Rank, ApplNo, RollNo, Name, DOB, Category, Community
            - **Total Statistics**: Total Marks, Total Correct, Total Wrong, Total Unattempted
            - **Section Marks**: English Marks, GK Marks, Arithmetic Marks, Legal Marks
            - **Section-wise Detailed Statistics**: 
              - Correct, Wrong, Unattempted counts for each section (English, GK, Arithmetic, Legal)
            """)

if __name__ == "__main__":
    main()
