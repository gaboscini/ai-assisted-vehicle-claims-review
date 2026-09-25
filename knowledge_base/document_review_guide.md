# Document Review Guide

KTP, SIM, and STNK are checked for completeness, readability, field confidence, consistency with the policy record, and validity on the incident date.

## KTP checks

The KTP review checks the identity number, full name, date of birth, and address.

- Identity number: at least 90% extraction confidence and an exact normalized match.
- Full name: at least 90% extraction confidence and at least a 90% name-match score.
- Date of birth: at least 85% extraction confidence and an exact date match.
- Address: at least 80% extraction confidence. It is informational and is not treated as a critical identity match.

## SIM checks

The SIM review checks the licence number, driver name, licence class, and expiration date.

- SIM number: at least 90% extraction confidence and an exact normalized match.
- Driver name: at least 90% extraction confidence and at least a 90% name-match score.
- Licence class: at least 80% extraction confidence and an exact normalized match.
- Expiration date: at least 90% extraction confidence and valid on the incident date.

An expired SIM is sent to claims staff for review.

## STNK checks

The STNK review checks the registered owner, plate number, vehicle make, model, year, chassis number, engine number, and registration expiration date.

- Registered owner and plate number: at least 90% extraction confidence.
- Vehicle make, model, and year: at least 85% extraction confidence.
- Chassis and engine numbers: at least 95% extraction confidence.
- Registration expiration date: at least 90% extraction confidence and valid on the incident date.

Names use a minimum 90% match score. Vehicle identifiers are expected to match the policy record after spacing and case are normalized.

## Understanding confidence and match scores

Extraction confidence measures how clearly a value was read from the uploaded document. A match score measures how closely the extracted value agrees with the policy or customer record.

A high extraction confidence does not guarantee a match. For example, a plate number can be read with 99% confidence but still differ from the insured plate number.

## Document outcomes

- Pass: the required value met its confidence and validation rules.
- Review: the value was read but needs claims-officer verification because of low confidence, mismatch, or expiration.
- Fail: a required document or field could not be accepted.
- Not scored: the field is informational or no reliable score is available.

Missing documents require additional information. Mismatches, expired documents, and low-confidence critical fields are routed to claims staff and do not automatically determine the final claim outcome.
