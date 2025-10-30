def create_na_permission_document(profile):
    """Creates a mock Non-Agricultural (NA) Permission Certificate PDF."""
    pdf = PDF()
    pdf.add_page()
    pdf.set_font('Helvetica', 'B', 16)
    pdf.cell(0, 10, 'NON-AGRICULTURAL (NA) PERMISSION CERTIFICATE', align='C', new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(10)

    pdf.set_font('Helvetica', '', 11)
    pdf.cell(0, 7, f"Date: {datetime.now().strftime('%d %B, %Y')}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.cell(0, 7, f"Ref No: NA/{random.randint(1000,9999)}/{datetime.now().year}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(10)

    pdf.set_font('Helvetica', 'BU', 12)
    pdf.cell(0, 10, "Subject: Conversion of Agricultural Land to Non-Agricultural Use", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(5)

    pdf.set_font('Helvetica', '', 11)
    text = (
        f"This is to certify that the land located at **{profile['property_address']}**, "
        f"owned by **{profile['name']} (PAN: {profile['pan']})**, "
        f"has been duly verified and approved for **Non-Agricultural (NA)** use "
        f"by the competent local authority.\n\n"
        f"The said property can be used for residential and commercial construction purposes. "
        f"No legal disputes or restrictions are found on the said land parcel as per the latest records."
    )
    pdf.multi_cell(0, 7, text, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(10)

    pdf.set_font('Helvetica', 'B', 12)
    pdf.cell(0, 10, f"Property Valuation (for record): INR {profile['property_valuation']:,.2f}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(15)

    pdf.set_font('Helvetica', '', 11)
    pdf.cell(0, 7, "Authorized Signatory,", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.cell(0, 7, "Department of Urban Development", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.cell(0, 7, "Government of Haryana", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    filename = os.path.join(OUTPUT_DIR, "na_permission_certificate.pdf")
    pdf.output(filename)
    print(f"Successfully created: {filename}")
